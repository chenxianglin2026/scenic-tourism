/**
 * 个人中心 - 订单 + 电子票 + 实名
 * 对接后端: GET /api/auth/me, GET /api/tickets/orders, GET /api/hotels/orders
 */
const api = require('../../utils/api')
const { ORDER_STATUS, PAGE_SIZE } = require('../../utils/const')

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
    activeTab: 'tickets', // 'tickets' | 'hotels'
    // 票务订单
    ticketOrders: [],
    loadingTickets: false,
    ticketsTotal: 0,
    ticketsPage: 1,
    // 客房订单
    hotelOrders: [],
    loadingHotels: false,
    hotelsTotal: 0,
    hotelsPage: 1,
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
      // 加载用户信息
      this.loadUserProfile()
    }
  },

  // 加载用户信息
  async loadUserProfile() {
    try {
      const user = await api.get('/api/auth/me')
      const app = getApp()
      app.globalData.userInfo = user
      this.setData({
        userInfo: user,
        phoneNumber: user.phone || this.data.phoneNumber
      })
    } catch (err) {
      // 忽略
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
    }
  },

  // 加载票务订单 → GET /api/tickets/orders
  async loadTicketOrders() {
    this.setData({ loadingTickets: true })
    try {
      const res = await api.get('/api/tickets/orders', {
        page: this.data.ticketsPage,
        page_size: PAGE_SIZE
      })
      // 后端返回 {total, items}
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : [])
      const total = (res && res.total) ? res.total : items.length
      this.setData({ ticketOrders: items, ticketsTotal: total, loadingTickets: false })
    } catch (err) {
      // mock 降级
      this.setData({
        ticketOrders: [
          { id: 1, order_no: 'SC20260601001', ticket_type_name: '成人票', quantity: 2, total_price: 160, status: 'paid', visit_date: '2026-06-02', time_slot: '08:00-10:00', created_at: '2026-06-01 10:30' },
          { id: 2, order_no: 'SC20260528002', ticket_type_name: '家庭套票', quantity: 1, total_price: 180, status: 'verified', visit_date: '2026-05-29', time_slot: '08:00-10:00', created_at: '2026-05-28 15:20' }
        ],
        loadingTickets: false
      })
    }
  },

  // 加载客房订单 → GET /api/hotels/orders
  async loadHotelOrders() {
    this.setData({ loadingHotels: true })
    try {
      const res = await api.get('/api/hotels/orders', {
        page: this.data.hotelsPage,
        page_size: PAGE_SIZE
      })
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : [])
      const total = (res && res.total) ? res.total : items.length
      this.setData({ hotelOrders: items, hotelsTotal: total, loadingHotels: false })
    } catch (err) {
      // mock 降级
      this.setData({
        hotelOrders: [
          { id: 1, order_no: 'HT20260601001', room_name: '标准双人房', checkin_date: '2026-06-02', checkout_date: '2026-06-03', nights: 1, total_price: 388, status: 'paid', guest_name: '张三', guest_phone: '13800138001' }
        ],
        loadingHotels: false
      })
    }
  },

  // 查看订单详情
  onOrderDetail(e) {
    const { id } = e.currentTarget.dataset
    const orders = this.data.activeTab === 'tickets' ? this.data.ticketOrders : this.data.hotelOrders
    const order = orders.find(o => o.id === id)
    if (!order) return

    let content = ''
    if (this.data.activeTab === 'tickets') {
      content = `订单号: ${order.order_no}\n票种: ${order.ticket_type_name || ''}\n数量: ${order.quantity}张\n金额: ¥${order.total_price}\n日期: ${order.visit_date} ${order.time_slot || ''}\n状态: ${ORDER_STATUS[order.status]?.label || order.status}`
    } else {
      content = `订单号: ${order.order_no}\n房型: ${order.room_name || ''}\n入住: ${order.checkin_date || order.check_in}\n离店: ${order.checkout_date || order.check_out}\n晚数: ${order.nights || 1}晚\n金额: ¥${order.total_price || order.amount}\n住客: ${order.guest_name}\n状态: ${order.status}`
    }

    wx.showModal({
      title: '订单详情',
      content,
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
  },

  // 常见问题
  onFaq() {
    wx.navigateTo({ url: '/pages/faq/faq' })
  }
})
