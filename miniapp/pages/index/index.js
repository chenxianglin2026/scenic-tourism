/**
 * 首页 - 景区介绍 + 快捷入口 + 公告
 */
const api = require('../../utils/api')
const { TICKET_TYPES } = require('../../utils/const')

Page({
  data: {
    scenic: {},
    notices: [],
    currentNotice: 0,
    tickets: [],
    // 轮播图片
    banners: [
      { id: 1, src: '/images/banner1.png' },
      { id: 2, src: '/images/banner2.png' },
      { id: 3, src: '/images/banner3.png' }
    ],
    loading: true
  },

  onLoad() {
    this.loadScenicInfo()
    this.loadNotices()
    this.loadTickets()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
  },

  onPullDownRefresh() {
    Promise.all([
      this.loadScenicInfo(),
      this.loadNotices(),
      this.loadTickets()
    ]).finally(() => wx.stopPullDownRefresh())
  },

  // 加载景区信息
  async loadScenicInfo() {
    try {
      const scenic = await api.get('/api/scenic/info')
      this.setData({ scenic, loading: false })
    } catch (err) {
      // 使用全局默认景区数据
      const app = getApp()
      this.setData({ scenic: app.globalData.currentScenic, loading: false })
    }
  },

  // 加载公告
  async loadNotices() {
    try {
      const notices = await api.get('/api/scenic/notices', { limit: 5 })
      this.setData({ notices })
    } catch (err) {
      // mock 数据
      this.setData({
        notices: [
          { id: 1, title: '端午节假期营业时间调整通知', time: '2026-06-05', content: '端午节期间正常营业，营业时间不变。' },
          { id: 2, title: '西湖景区部分区域维护公告', time: '2026-05-20', content: '苏堤南段进行景观维护，请游客绕行。' },
          { id: 3, title: '学生票优惠活动延长至8月底', time: '2026-05-01', content: '全日制学生凭学生证享受半价优惠。' }
        ]
      })
    }
  },

  // 加载热门票种
  async loadTickets() {
    try {
      const tickets = await api.get('/api/tickets/types', { limit: 4 })
      this.setData({ tickets })
    } catch (err) {
      this.setData({
        tickets: [
          { id: 1, name: '成人票', price: 80, label: '18-60周岁' },
          { id: 2, name: '儿童票', price: 40, label: '6-18周岁' },
          { id: 3, name: '老年票', price: 40, label: '60周岁以上' },
          { id: 4, name: '家庭套票', price: 180, label: '2大1小' }
        ]
      })
    }
  },

  // 公告切换
  onNoticeTap(e) {
    const { id } = e.currentTarget.dataset
    wx.showModal({
      title: this.data.notices[id].title,
      content: this.data.notices[id].content,
      showCancel: false
    })
  },

  // 快捷入口跳转
  onQuickEntry(e) {
    const { type } = e.currentTarget.dataset
    switch (type) {
      case 'tickets':
        wx.switchTab({ url: '/pages/tickets/tickets' })
        break
      case 'hotels':
        wx.switchTab({ url: '/pages/hotels/hotels' })
        break
      case 'mine':
        wx.switchTab({ url: '/pages/mine/mine' })
        break
      case 'scenic':
        wx.showModal({
          title: this.data.scenic.name || '景区介绍',
          content: this.data.scenic.description || '欢迎来到美丽的景区！',
          showCancel: false
        })
        break
    }
  },

  // 购票跳转
  onBuyTicket(e) {
    const { id } = e.currentTarget.dataset
    wx.switchTab({ url: '/pages/tickets/tickets' })
  }
})
