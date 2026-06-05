/**
 * 首页 - 景区介绍 + 快捷入口 + 公告
 * 对接后端: GET /api/hotels, GET /api/tickets/types
 * 景区信息和公告为本地数据（后端暂无这些接口）
 */
const api = require('../../utils/api')

Page({
  data: {
    scenic: {},
    notices: [],
    tickets: [],
    hotels: [],
    // 轮播图片
    banners: [
      { id: 1, title: '西湖风景' },
      { id: 2, title: '灵隐禅寺' },
      { id: 3, title: '雷峰夕照' }
    ],
    loading: true
  },

  onLoad() {
    this.loadScenicInfo()
    this.loadNotices()
    this.loadTickets()
    this.loadHotels()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
  },

  onPullDownRefresh() {
    Promise.all([
      this.loadTickets(),
      this.loadHotels()
    ]).finally(() => wx.stopPullDownRefresh())
  },

  // 加载景区信息（本地数据，后端暂无 /api/scenic/info）
  loadScenicInfo() {
    const app = getApp()
    this.setData({ scenic: app.globalData.currentScenic, loading: false })
  },

  // 加载公告（本地数据）
  loadNotices() {
    // 后端暂无公告接口，使用本地 mock
    this.setData({
      notices: [
        { id: 1, title: '端午节假期营业时间调整通知', time: '2026-06-05', content: '端午节期间正常营业，营业时间不变。' },
        { id: 2, title: '西湖景区部分区域维护公告', time: '2026-05-20', content: '苏堤南段进行景观维护，请游客绕行。' },
        { id: 3, title: '学生票优惠活动延长至8月底', time: '2026-05-01', content: '全日制学生凭学生证享受半价优惠。' }
      ]
    })
  },

  // 加载热门票种 → GET /api/tickets/types
  async loadTickets() {
    try {
      const spotId = getApp().globalData.currentScenic?.id || 1
      const types = await api.get('/api/tickets/types', { spot_id: spotId })
      // 取前4个展示
      const tickets = (types || []).slice(0, 4).map(t => ({
        id: t.id,
        name: t.name,
        price: t.price,
        label: t.description || t.category || ''
      }))
      this.setData({ tickets })
    } catch (err) {
      // mock 降级
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

  // 加载酒店 → GET /api/hotels
  async loadHotels() {
    try {
      const spotId = getApp().globalData.currentScenic?.id || 1
      const hotels = await api.get('/api/hotels', { spot_id: spotId })
      this.setData({ hotels: hotels || [] })
    } catch (err) {
      // mock 降级
      this.setData({
        hotels: [
          { id: 1, name: '西湖大酒店', rating: 4.8, address: '杭州市西湖区' }
        ]
      })
    }
  },

  // 公告切换
  onNoticeTap(e) {
    const { id } = e.currentTarget.dataset
    const notice = this.data.notices[id]
    if (notice) {
      wx.showModal({
        title: notice.title,
        content: notice.content,
        showCancel: false
      })
    }
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
