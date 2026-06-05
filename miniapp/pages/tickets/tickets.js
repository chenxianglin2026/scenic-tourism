/**
 * 票务页 - 票种选择 + 分时 + 购票 + 二维码
 */
const api = require('../../utils/api')
const { TICKET_TYPES, TIME_SLOTS, ORDER_STATUS } = require('../../utils/const')

Page({
  data: {
    // 票种列表
    ticketTypes: [],
    // 时段列表
    timeSlots: [],
    // 当前选择
    selectedType: null,
    selectedSlot: null,
    quantity: 1,
    visitDate: '',
    // 订单
    currentOrder: null,
    orderQR: '',
    // 实名信息
    realName: '',
    idCard: '',
    needRealName: false,
    // 视图切换: 'shop' | 'order' | 'qr'
    viewMode: 'shop',
    // 价格
    unitPrice: 0,
    totalPrice: 0,
    loading: true
  },

  onLoad() {
    const today = new Date()
    const dateStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`
    this.setData({ visitDate: dateStr })
    this.loadTicketTypes()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    // 检查实名信息
    const realName = wx.getStorageSync('realName') || ''
    const idCard = wx.getStorageSync('idCard') || ''
    this.setData({ realName, idCard })
  },

  // 加载票种
  async loadTicketTypes() {
    try {
      const types = await api.get('/api/tickets/types')
      this.setData({ ticketTypes: types, loading: false })
    } catch (err) {
      this.setData({
        ticketTypes: Object.entries(TICKET_TYPES).map(([key, val]) => ({
          id: key,
          name: val.label,
          icon: val.icon,
          desc: val.desc,
          price: key === 'family' ? 180 : key === 'annual' ? 365 : key === 'adult' ? 80 : 40
        })),
        loading: false
      })
    }

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
    this.setData({ selectedType: id, unitPrice: price })
    this.calcTotal()
  },

  // 选择时段
  onSelectSlot(e) {
    const { id } = e.currentTarget.dataset
    this.setData({ selectedSlot: id })
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
  onRealNameInput(e) {
    this.setData({ realName: e.detail.value })
  },

  onIdCardInput(e) {
    this.setData({ idCard: e.detail.value })
  },

  // 提交订单
  async onSubmitOrder() {
    const { selectedType, selectedSlot, quantity, visitDate, unitPrice } = this.data

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

    try {
      const order = await api.post('/api/tickets/orders', {
        ticket_type: selectedType,
        time_slot: selectedSlot,
        quantity,
        visit_date: visitDate,
        price: unitPrice
      })
      wx.hideLoading()
      this.setData({ currentOrder: order, viewMode: 'order' })
      // 保存实名信息
      if (this.data.realName) wx.setStorageSync('realName', this.data.realName)
      if (this.data.idCard) wx.setStorageSync('idCard', this.data.idCard)
    } catch (err) {
      wx.hideLoading()
      // mock 模式
      const mockOrder = {
        id: Date.now(),
        orderNo: 'SC' + Date.now(),
        ticket_type: selectedType,
        time_slot: selectedSlot,
        quantity,
        total_price: this.data.totalPrice,
        status: 'unpaid',
        create_time: new Date().toISOString()
      }
      this.setData({ currentOrder: mockOrder, viewMode: 'order' })
    }
  },

  // 去支付（mock）
  onPayOrder() {
    wx.showLoading({ title: '支付中...' })
    setTimeout(() => {
      wx.hideLoading()
      const order = { ...this.data.currentOrder, status: 'paid' }
      this.setData({ currentOrder: order, viewMode: 'qr' })
      // 生成模拟二维码内容
      this.setData({ orderQR: JSON.stringify({ orderNo: order.orderNo, id: order.id }) })
      wx.showToast({ title: '支付成功', icon: 'success' })
    }, 1500)
  },

  // 返回购票
  onBackToShop() {
    this.setData({ viewMode: 'shop', currentOrder: null, orderQR: '' })
  },

  // 查看我的订单
  onViewMyOrders() {
    wx.switchTab({ url: '/pages/mine/mine' })
  }
})
