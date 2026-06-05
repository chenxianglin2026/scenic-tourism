/**
 * 首页 - 景区介绍 + 快捷入口 + 公告 + 热门票种
 * 对接后端: GET /api/scenic/info, /api/scenic/announcements, /api/tickets/types, /api/hotels
 */
const api = require('../../utils/api')

Page({
  data: {
    scenic: {},
    notices: [],
    tickets: [],
    hotels: [],
    banners: [
      { id: 1, title: '泰山日出', subtitle: '登泰山而小天下' },
      { id: 2, title: '云海奇观', subtitle: '仙境般的云海日出' },
      { id: 3, title: '古刹禅意', subtitle: '千年文化底蕴' }
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
      this.loadScenicInfo(),
      this.loadNotices(),
      this.loadTickets(),
      this.loadHotels()
    ]).finally(() => wx.stopPullDownRefresh())
  },

  // 加载景区信息 → GET /api/scenic/info
  async loadScenicInfo() {
    try {
      const data = await api.get('/api/scenic/info')
      const scenic = {
        id: data.id,
        name: data.name || '泰山风景名胜区',
        address: data.address || '',
        phone: data.phone || '',
        description: data.description || '',
        openTime: (data.open_time && data.close_time)
          ? `${data.open_time}-${data.close_time}`
          : (data.open_time || '06:00-18:00'),
        rating: data.rating || 4.8,
        cover_image: data.cover_image || '',
        lat: data.lat,
        lng: data.lng
      }
      this.setData({ scenic, loading: false })
    } catch (err) {
      // 降级使用 app globalData
      const app = getApp()
      this.setData({
        scenic: app.globalData.currentScenic || {
          name: '泰山风景名胜区',
          address: '山东省泰安市',
          openTime: '06:00-18:00',
          rating: 4.8
        },
        loading: false
      })
    }
  },

  // 加载公告 → GET /api/scenic/announcements
  async loadNotices() {
    try {
      const data = await api.get('/api/scenic/announcements')
      const items = data.items || data || []
      const notices = items.slice(0, 5).map(item => ({
        id: item.id,
        title: item.title,
        time: item.published_at ? item.published_at.slice(0, 10) : '',
        content: item.content || '',
        category: item.category || 'notice'
      }))
      this.setData({ notices })
    } catch (err) {
      // mock 降级
      this.setData({
        notices: [
          { id: 1, title: '端午节特惠活动通知', time: '2026-06-05', content: '端午节期间推出家庭套票优惠活动，两大一小仅需258元。' },
          { id: 2, title: '南天门索道维护公告', time: '2026-05-20', content: '索道将于6月15日-17日暂停运营，请步行登山。' },
          { id: 3, title: '夏季开放时间调整通知', time: '2026-05-01', content: '夏季运营时间调整为05:30-19:00。' }
        ]
      })
    }
  },

  // 加载热门票种 → GET /api/tickets/types
  async loadTickets() {
    try {
      const spotId = getApp().globalData.currentScenic?.id || 1
      const types = await api.get('/api/tickets/types', { spot_id: spotId })
      const tickets = (types || []).slice(0, 4).map(t => ({
        id: t.id,
        name: t.name,
        price: t.price,
        label: t.description || t.category || ''
      }))
      this.setData({ tickets })
    } catch (err) {
      this.setData({
        tickets: [
          { id: 1, name: '成人票', price: 115, label: '18-59周岁' },
          { id: 2, name: '儿童票', price: 57, label: '6-17周岁' },
          { id: 3, name: '老人票', price: 57, label: '60周岁以上' },
          { id: 4, name: '团体票', price: 90, label: '10人起订' }
        ]
      })
    }
  },

  // 加载酒店 → GET /api/hotels
  async loadHotels() {
    try {
      const spotId = getApp().globalData.currentScenic?.id || 1
      const hotels = await api.get('/api/hotels', { spot_id: spotId })
      this.setData({ hotels: (hotels || []).slice(0, 3) })
    } catch (err) {
      this.setData({
        hotels: [
          { id: 1, name: '泰山大酒店', rating: 4.8, address: '泰安市泰山区' }
        ]
      })
    }
  },

  // 公告展开详情
  onNoticeTap(e) {
    const { id } = e.currentTarget.dataset
    const notice = this.data.notices.find(n => n.id == id)
    if (notice) {
      wx.showModal({
        title: notice.title,
        content: notice.content,
        showCancel: false,
        confirmText: '我知道了'
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
      case 'scenic':
        wx.navigateTo({ url: '/pages/scenic/scenic' })
        break
      case 'parking':
        wx.navigateTo({ url: '/pages/parking/parking' })
        break
    }
  },

  // 购票跳转
  onBuyTicket(e) {
    wx.switchTab({ url: '/pages/tickets/tickets' })
  }
})
