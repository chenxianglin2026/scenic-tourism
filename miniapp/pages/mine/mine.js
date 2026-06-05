/**
 * 个人中心 - 订单 + 电子票 + 实名
 */
const api = require('../../utils/api')
const { ORDER_STATUS } = require('../../utils/const')

Page({
  data: {
    // 用户
    isLogin: false,
    userInfo: null,
    phoneNumber: '',
    // 实名信息
    realName: '',
    idCard: '',
    showRealNameModal: false,
    // Tab
    activeTab: 'tickets', // 'tickets' | 'hotels' | 'etickets'
    // 票务订单
    ticketOrders: [],
    loadingTickets: false,
    // 客房订单
    hotelOrders: [],
    loadingHotels: false,
    // 电子票
    eTickets: [],
    loadingETickets: false
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 3 })
    }
    this.checkLoginStatus()
    this.loadRealName()
  },

  // 检查登录状态
  checkLoginStatus() {
    const token = wx.getStorageSync('token')
    const app = getApp()
    this.setData({
      isLogin: !!token,
      userInfo: app.globalData.userInfo || null,
      phoneNumber: app.globalData.phoneNumber || ''
    })

    if (token) {
      this.loadTicketOrders()
    }
  },

  // 加载实名信息
  loadRealName() {
    this.setData({
      realName: wx.getStorageSync('realName') || '',
      idCard: wx.getStorageSync('idCard') || ''
    })
  },

  // 微信登录
  onWxLogin() {
    const app = getApp()
    app.wxLogin((success) => {
      if (success) {
        this.setData({
          isLogin: true,
          userInfo: app.globalData.userInfo,
          phoneNumber: app.globalData.phoneNumber
        })
        this.loadTicketOrders()
        wx.showToast({ title: '登录成功', icon: 'success' })
      } else {
        wx.showToast({ title: '登录失败', icon: 'none' })
      }
    })
  },

  // 获取手机号
  onGetPhoneNumber(e) {
    const app = getApp()
    app.getPhoneNumber(e, (success, phone) => {
      if (success) {
        this.setData({ phoneNumber: phone })
        wx.showToast({ title: '绑定成功', icon: 'success' })
      }
    })
  },

  // Tab 切换
  onTabChange(e) {
    const { tab } = e.currentTarget.dataset
    this.setData({ activeTab: tab })

    if (tab === 'tickets' && this.data.ticketOrders.length === 0) {
      this.loadTicketOrders()
    } else if (tab === 'hotels' && this.data.hotelOrders.length === 0) {
      this.loadHotelOrders()
    } else if (tab === 'etickets' && this.data.eTickets.length === 0) {
      this.loadETickets()
    }
  },

  // 加载票务订单
  async loadTicketOrders() {
    this.setData({ loadingTickets: true })
    try {
      const orders = await api.get('/api/tickets/orders/my')
      this.setData({ ticketOrders: orders, loadingTickets: false })
    } catch (err) {
      this.setData({
        ticketOrders: [
          { id: 1, order_no: 'SC20260601001', ticket_type: '成人票', quantity: 2, total_price: 160, status: 'paid', visit_date: '2026-06-02', time_slot: '全天', create_time: '2026-06-01 10:30' },
          { id: 2, order_no: 'SC20260528002', ticket_type: '家庭套票', quantity: 1, total_price: 180, status: 'verified', visit_date: '2026-05-29', time_slot: '上午场', create_time: '2026-05-28 15:20' }
        ],
        loadingTickets: false
      })
    }
  },

  // 加载客房订单
  async loadHotelOrders() {
    this.setData({ loadingHotels: true })
    try {
      const orders = await api.get('/api/hotels/orders/my')
      this.setData({ hotelOrders: orders, loadingHotels: false })
    } catch (err) {
      this.setData({
        hotelOrders: [
          { id: 1, order_no: 'HT20260601001', room_name: '标准双人房', check_in: '2026-06-02', check_out: '2026-06-03', amount: 388, status: 'paid', guest_name: '张三' }
        ],
        loadingHotels: false
      })
    }
  },

  // 加载电子票
  async loadETickets() {
    this.setData({ loadingETickets: true })
    try {
      const tickets = await api.get('/api/tickets/etickets/my')
      this.setData({ eTickets: tickets, loadingETickets: false })
    } catch (err) {
      this.setData({
        eTickets: [
          { id: 1, order_no: 'SC20260528002', ticket_type: '家庭套票', quantity: 1, status: 'verified', visit_date: '2026-05-29', time_slot: '上午场', verify_time: '2026-05-29 09:15' }
        ],
        loadingETickets: false
      })
    }
  },

  // 查看订单详情
  onOrderDetail(e) {
    const { id } = e.currentTarget.dataset
    const orders = this.data.activeTab === 'tickets' ? this.data.ticketOrders : this.data.hotelOrders
    const order = orders.find(o => o.id === id)
    if (!order) return

    const info = order.order_no
      ? `订单号: ${order.order_no}\n金额: ¥${order.total_price || order.amount}\n状态: ${ORDER_STATUS[order.status]?.label || order.status}`
      : '暂无详情'

    wx.showModal({
      title: '订单详情',
      content: info,
      showCancel: false
    })
  },

  // 显示电子票二维码
  onShowQR(e) {
    const { id } = e.currentTarget.dataset
    const ticket = this.data.eTickets.find(t => t.id === id)
    if (!ticket) return
    wx.showModal({
      title: '电子票',
      content: `票种: ${ticket.ticket_type}\n数量: ${ticket.quantity}张\n订单号: ${ticket.order_no}\n入园日期: ${ticket.visit_date}\n核销时间: ${ticket.verify_time || '未核销'}`,
      showCancel: false
    })
  },

  // 实名认证
  onEditRealName() {
    this.setData({ showRealNameModal: true })
  },

  onCloseRealNameModal() {
    this.setData({ showRealNameModal: false })
    this.loadRealName()
  },

  onRealNameInput(e) {
    this.setData({ realName: e.detail.value })
  },

  onIdCardInput(e) {
    this.setData({ idCard: e.detail.value })
  },

  onSaveRealName() {
    const { realName, idCard } = this.data
    if (!realName || !idCard) {
      wx.showToast({ title: '请填写完整信息', icon: 'none' })
      return
    }
    wx.setStorageSync('realName', realName)
    wx.setStorageSync('idCard', idCard)
    this.setData({ showRealNameModal: false })
    wx.showToast({ title: '保存成功', icon: 'success' })
  },

  // 退出登录
  onLogout() {
    wx.showModal({
      title: '提示',
      content: '确定要退出登录吗？',
      success(res) {
        if (res.confirm) {
          wx.removeStorageSync('token')
          wx.removeStorageSync('realName')
          wx.removeStorageSync('idCard')
          const app = getApp()
          app.globalData.token = ''
          app.globalData.userInfo = null
          app.globalData.phoneNumber = ''
          wx.reLaunch({ url: '/pages/mine/mine' })
        }
      }
    })
  },

  // 联系客服
  onContact() {
    wx.makePhoneCall({ phoneNumber: '0571-88886666' })
  }
})
