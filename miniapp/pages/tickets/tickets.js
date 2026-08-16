/**
 * 票务页 - 票种选择 + 分时 + 购票 + 二维码
 * 对接后端: GET /api/tickets/types, POST /api/tickets/order, GET /api/tickets/orders
 */
const api = require('../../utils/api')
const { TICKET_TYPES, TIME_SLOTS, ORDER_STATUS } = require('../../utils/const')
const { generateQRMatrix, drawQRToCanvasContext } = require('../../utils/qrcode')
const { requestPayment } = require('../../utils/payment')

Page({
  data: {
    // 票种列表（从后端加载）
    ticketTypes: [],
    // 时段列表
    timeSlots: [],
    // 当前选择
    selectedType: null,
    selectedSlot: null,
    quantity: 1,
    visitDate: '',
    // 当前景区ID
    spotId: 1,
    // 订单
    currentOrder: null,
    orderQR: '',
    // 实名信息
    visitorName: '',
    visitorPhone: '',
    visitorIdCard: '',
    // 视图切换: 'shop' | 'order' | 'qr'
    viewMode: 'shop',
    // 价格
    unitPrice: 0,
    totalPrice: 0,
    loading: true,
    submitting: false,
    // 二维码canvas尺寸
    qrCanvasSize: 300,
    // 动态二维码倒计时（秒）
    qrCountdown: 30,
    // 拼团折扣阶梯
    groupBuyTiers: [],
    showGroupBuy: false,
    // 先玩后付额度
    payLaterQuota: 0,
    showPayLater: false,
  },

  onLoad() {
    const today = new Date()
    const dateStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`
    const app = getApp()
    this.setData({
      visitDate: dateStr,
      spotId: (app.globalData.currentScenic || {}).id || 1
    })
    this.loadTicketTypes()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    // 恢复实名信息
    const visitorName = wx.getStorageSync('realName') || ''
    const visitorIdCard = wx.getStorageSync('idCard') || ''
    this.setData({ visitorName, visitorIdCard })
  },

  // 加载票种（真实API + mock降级）
  async loadTicketTypes() {
    try {
      const types = await api.get('/api/tickets/types', { spot_id: this.data.spotId })
      this.setData({
        ticketTypes: types,
        loading: false
      })
    } catch (err) {
      // API 不可用时用本地 mock
      this.setData({
        ticketTypes: [
          { id: 1, name: '成人票', price: 80, category: 'adult', description: '18-60周岁成人' },
          { id: 2, name: '儿童票', price: 40, category: 'child', description: '6-18周岁儿童' },
          { id: 3, name: '老年票', price: 40, category: 'senior', description: '60周岁以上老人' },
          { id: 4, name: '学生票', price: 40, category: 'student', description: '全日制学生' },
          { id: 5, name: '家庭套票', price: 180, category: 'family', description: '2大1小家庭套票' },
          { id: 6, name: '年卡', price: 365, category: 'annual', description: '全年不限次入园' },
        ],
        loading: false
      })
    }

    // 时段从常量加载
    this.setData({
      timeSlots: Object.entries(TIME_SLOTS).map(([key, val]) => ({
        id: key,
        label: val.label,
        time: val.time,
        desc: val.desc
      }))
    })
  },

  // 选择票种
  onSelectType(e) {
    const { id, price } = e.currentTarget.dataset
    this.setData({ selectedType: id, unitPrice: price || 0 })
    this.calcTotal()
  },

  // 选择时段
  onSelectSlot(e) {
    const { id, time } = e.currentTarget.dataset
    this.setData({ selectedSlot: time })  // 存储实际 time_slot 值如 "08:00-10:00"
  },

  // 数量变更
  onQuantityChange(e) {
    const { type } = e.currentTarget.dataset
    let qty = this.data.quantity
    if (type === 'plus' && qty < 10) qty++
    if (type === 'minus' && qty > 1) qty--
    this.setData({ quantity: qty })
    this.calcTotal()
  },

  // 日期选择
  onDateChange(e) {
    this.setData({ visitDate: e.detail.value })
  },

  // 计算总价
  calcTotal() {
    this.setData({ totalPrice: this.data.unitPrice * this.data.quantity })
  },

  // 实名输入
  onVisitorNameInput(e) {
    this.setData({ visitorName: e.detail.value })
  },

  onVisitorPhoneInput(e) {
    this.setData({ visitorPhone: e.detail.value })
  },

  onVisitorIdCardInput(e) {
    this.setData({ visitorIdCard: e.detail.value })
  },

  // 提交订单 → POST /api/tickets/order
  async onSubmitOrder() {
    if (this.data.submitting) return
    const { selectedType, selectedSlot, quantity, visitDate, visitorName, visitorPhone, visitorIdCard, spotId } = this.data

    if (!selectedType) {
      wx.showToast({ title: '请选择票种', icon: 'none' })
      return
    }
    if (!selectedSlot) {
      wx.showToast({ title: '请选择时段', icon: 'none' })
      return
    }

    // 检查登录
    const token = wx.getStorageSync('token')
    if (!token) {
      wx.showModal({
        title: '提示',
        content: '请先在「我的」页面登录',
        confirmText: '去登录',
        success(res) {
          if (res.confirm) wx.switchTab({ url: '/pages/mine/mine' })
        }
      })
      return
    }

    wx.showLoading({ title: '提交中...' })
    this.setData({ submitting: true })

    try {
      const orderData = {
        ticket_type_id: parseInt(selectedType),
        spot_id: spotId,
        quantity: quantity,
        visit_date: visitDate,
        time_slot: selectedSlot,
        visitor_name: visitorName || undefined,
        visitor_phone: visitorPhone || undefined,
        visitor_id_card: visitorIdCard || undefined,
      }
      const order = await api.post('/api/tickets/order', orderData)
      wx.hideLoading()

      // 保存实名信息
      if (visitorName) wx.setStorageSync('realName', visitorName)
      if (visitorIdCard) wx.setStorageSync('idCard', visitorIdCard)

      // 转换为展示格式
      this.setData({
        currentOrder: this._formatOrder(order),
        viewMode: 'order',
        submitting: false
      })
    } catch (err) {
      wx.hideLoading()
      // API失败时 mock 降级
      if (err.code === -1 || err.code === 404) {
        const orderNo = 'SC' + Date.now()
        this.setData({
          currentOrder: {
            id: Date.now(),
            order_no: orderNo,
            ticket_type_name: (this.data.ticketTypes.find(t => t.id === selectedType) || {}).name || '门票',
            quantity,
            total_price: this.data.totalPrice,
            status: 'pending',
            visit_date: visitDate,
            time_slot: selectedSlot,
            created_at: new Date().toISOString(),
            qr_token: orderNo,
          },
          viewMode: 'order'
        })
        wx.showToast({ title: '已生成模拟订单', icon: 'none' })
        this.setData({ submitting: false })
      }
    }
  },

  // 格式化订单（前端展示用）
  _formatOrder(order) {
    return {
      id: order.id,
      order_no: order.order_no,
      ticket_type_name: order.ticket_type_name || '',
      quantity: order.quantity,
      total_price: order.total_price,
      status: order.status,
      visit_date: order.visit_date,
      time_slot: order.time_slot,
      qr_token: order.qr_token,
      created_at: order.created_at,
    }
  },

  // 去支付 → 微信支付真实流程
  async onPayOrder() {
    if (this.data.submitting) return
    const { currentOrder, totalPrice } = this.data
    if (!currentOrder) return

    this.setData({ submitting: true })

    try {
      // 调用微信支付: 后端创建预付单 → wx.requestPayment 拉起支付
      await requestPayment({
        orderNo: currentOrder.order_no,
        orderType: 'ticket',
        totalFee: Math.round((totalPrice || currentOrder.total_price || 0) * 100), // 元→分
        desc: currentOrder.ticket_type_name || '景区门票'
      })

      // 支付成功 → 更新状态并展示二维码
      const orderQR = currentOrder.qr_token || currentOrder.order_no
      this.setData({
        currentOrder: { ...currentOrder, status: 'paid' },
        viewMode: 'qr',
        orderQR,
        submitting: false
      })
      // 延迟绘制二维码（等待canvas节点就绪）
      setTimeout(() => this.drawOrderQR(orderQR), 300)
      // 启动动态二维码刷新（30秒轮询新 token 防伪）
      this.startDynamicQR()
      wx.showToast({ title: '支付成功', icon: 'success' })
    } catch (err) {
      this.setData({ submitting: false })
      // 用户取消支付不弹错误提示
      if (err && err.errMsg && err.errMsg.indexOf('cancel') !== -1) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
      }
      // 其他错误已在 payment.js 中处理
    }
  },

  // 绘制订单二维码到canvas
  drawOrderQR(qrToken) {
    if (!qrToken) return
    try {
      const qrData = generateQRMatrix(qrToken)
      const ctx = wx.createCanvasContext('orderQrCanvas', this)
      const size = this.data.qrCanvasSize
      drawQRToCanvasContext(ctx, qrData.matrix, qrData.size, size, size)
      ctx.draw()
    } catch (e) {
      console.error('QR绘制失败:', e)
    }
  },

  // 返回购票
  onBackToShop() {
    this.setData({ viewMode: 'shop', currentOrder: null, orderQR: '' })
    this.stopDynamicQR()
  },

  // 查看我的订单
  onViewMyOrders() {
    this.stopDynamicQR()
    wx.switchTab({ url: '/pages/mine/mine' })
  },

  // ===== 动态二维码（五大购票升级 #3）=====
  startDynamicQR() {
    this.stopDynamicQR()
    this.setData({ qrCountdown: 30 })
    this._qrTimer = setInterval(() => {
      const next = this.data.qrCountdown - 1
      if (next <= 0) {
        this.refreshDynamicQR()
      } else {
        this.setData({ qrCountdown: next })
      }
    }, 1000)
  },

  stopDynamicQR() {
    if (this._qrTimer) { clearInterval(this._qrTimer); this._qrTimer = null }
  },

  async refreshDynamicQR() {
    this.setData({ qrCountdown: 30 })
    const orderNo = this.data.currentOrder && this.data.currentOrder.order_no
    if (!orderNo) return
    try {
      const data = await api.get(`/api/packages/qr/dynamic/${orderNo}`)
      const newToken = (data && (data.qr_token || data.token)) || orderNo
      this.setData({ orderQR: newToken })
      this.drawOrderQR(newToken)
    } catch (err) {
      // 刷新失败保持原二维码，下一轮重试
    }
  },

  // ===== 拼团折扣（五大购票升级 #4）=====
  async onToggleGroupBuy() {
    if (this.data.showGroupBuy) { this.setData({ showGroupBuy: false }); return }
    try {
      const data = await api.get('/api/packages/group-buy/info')
      const tiers = (data && data.tiers) || []
      this.setData({ groupBuyTiers: tiers, showGroupBuy: true })
    } catch (err) {
      // 降级：展示默认阶梯
      this.setData({
        groupBuyTiers: [
          { people: 2, discount: 0.95 },
          { people: 5, discount: 0.90 },
          { people: 10, discount: 0.85 },
        ],
        showGroupBuy: true
      })
    }
  },

  // ===== 先玩后付（五大购票升级 #5）=====
  async onTogglePayLater() {
    if (this.data.showPayLater) { this.setData({ showPayLater: false }); return }
    try {
      const data = await api.get('/api/packages/pay-later/status')
      this.setData({ payLaterQuota: (data && data.quota) || 0, showPayLater: true })
    } catch (err) {
      this.setData({ payLaterQuota: 2000, showPayLater: true })
    }
  },

  onUnload() {
    this.stopDynamicQR()
  }
})
