/**
 * 附近推荐 - 景区周边餐饮/购物/娱乐推荐
 * 对接后端: GET /api/scenic/points
 */
const api = require('../../utils/api')

Page({
  data: {
    points: [],
    categories: [
      { key: 'all', label: '全部', icon: '🏠' },
      { key: 'dining', label: '餐饮', icon: '🍽️' },
      { key: 'shopping', label: '购物', icon: '🛍️' },
      { key: 'entertainment', label: '娱乐', icon: '🎭' }
    ],
    activeCategory: 'all',
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: true,
    loading: false,
    refreshing: false
  },

  onLoad() {
    this.loadPoints()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true, refreshing: true })
    this.loadPoints().finally(() => {
      wx.stopPullDownRefresh()
      this.setData({ refreshing: false })
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadPoints(true)
    }
  },

  // 加载附近推荐点位 → GET /api/scenic/points
  async loadPoints(append = false) {
    if (this.data.loading) return
    this.setData({ loading: true })

    const params = {
      page: append ? this.data.page + 1 : 1,
      page_size: this.data.pageSize
    }
    if (this.data.activeCategory !== 'all') {
      params.category = this.data.activeCategory
    }

    try {
      const spotId = getApp().globalData.currentScenic?.id
      if (spotId) params.spot_id = spotId

      const res = await api.get('/api/scenic/points', params)
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : [])
      const total = (res && res.total) ? res.total : items.length

      const points = append
        ? [...this.data.points, ...items]
        : items

      this.setData({
        points,
        total,
        page: append ? this.data.page + 1 : 1,
        hasMore: points.length < total,
        loading: false
      })
    } catch (err) {
      // mock 降级
      this.setData({
        points: [
          { id: 1, name: '泰山脚下农家菜馆', category: 'dining', description: '地道鲁菜，手工煎饼卷大葱', address: '红门路128号', rating: 4.5, distance: 0.8, price_range: '¥40-80/人', open_time: '09:00-21:00', phone: '0538-1234567' },
          { id: 2, name: '岱庙小吃街', category: 'dining', description: '汇集泰安特色小吃', address: '东岳大街66号', rating: 4.3, distance: 1.2, price_range: '¥15-40/人', open_time: '10:00-22:00' },
          { id: 3, name: '云海茶楼', category: 'dining', description: '品茗赏景，泰山女儿茶', address: '天外村广场旁', rating: 4.7, distance: 0.5, price_range: '¥30-60/人', open_time: '08:00-20:00' },
          { id: 4, name: '泰山特产商店', category: 'shopping', description: '泰山灵芝、泰山石敢当、泰山女儿茶', address: '红门路200号', rating: 4.2, distance: 0.6, price_range: '¥20-500', open_time: '08:00-18:00' },
          { id: 5, name: '文创纪念品店', category: 'shopping', description: '泰山主题文创产品、明信片', address: '天街18号', rating: 4.4, distance: 3.5, price_range: '¥10-200' },
          { id: 6, name: '泰山皮影戏馆', category: 'entertainment', description: '国家级非遗——泰山皮影戏表演', address: '岱庙北街12号', rating: 4.8, distance: 1.5, price_range: '¥60/人', open_time: '10:00-17:00', phone: '0538-8765432' },
          { id: 7, name: '封禅大典演出', category: 'entertainment', description: '大型山水实景演出，再现帝王封禅', address: '天烛峰景区', rating: 4.6, distance: 4.0, price_range: '¥188-588', open_time: '20:00-21:30' },
          { id: 8, name: '登山装备店', category: 'shopping', description: '登山杖、冲锋衣、登山鞋', address: '红门路98号', rating: 4.1, distance: 0.9, price_range: '¥30-800' }
        ],
        total: 8,
        hasMore: false,
        loading: false
      })
    }
  },

  // 切换分类
  onCategoryTap(e) {
    const { key } = e.currentTarget.dataset
    if (key === this.data.activeCategory) return
    this.setData({ activeCategory: key, page: 1, hasMore: true, points: [] })
    this.loadPoints()
  },

  // 查看详情
  onPointTap(e) {
    const { id } = e.currentTarget.dataset
    const point = this.data.points.find(p => p.id == id)
    if (!point) return

    const stars = '★'.repeat(Math.floor(point.rating || 0)) + '☆'.repeat(5 - Math.floor(point.rating || 0))
    let content = `${point.name}\n\n${stars} ${point.rating || '--'}分`
    if (point.description) content += `\n\n${point.description}`
    if (point.address) content += `\n📍 ${point.address}`
    if (point.distance !== null && point.distance !== undefined) content += `\n📏 距景区约 ${point.distance}km`
    if (point.price_range) content += `\n💰 ${point.price_range}`
    if (point.open_time) content += `\n🕐 ${point.open_time}`

    wx.showModal({
      title: '详情',
      content,
      showCancel: false,
      confirmText: '知道了'
    })
  },

  // 拨打电话
  onCall(e) {
    const { id } = e.currentTarget.dataset
    const point = this.data.points.find(p => p.id == id)
    if (point && point.phone) {
      wx.makePhoneCall({ phoneNumber: point.phone })
    } else {
      wx.showToast({ title: '暂无联系电话', icon: 'none' })
    }
  },

  // 导航
  onNavigate(e) {
    const { id } = e.currentTarget.dataset
    const point = this.data.points.find(p => p.id == id)
    if (point && point.lat && point.lng) {
      wx.openLocation({
        latitude: point.lat,
        longitude: point.lng,
        name: point.name,
        address: point.address || '',
        scale: 16
      })
    } else {
      wx.showToast({ title: '暂无位置信息', icon: 'none' })
    }
  },

  _categoryLabel(cat) {
    const map = { dining: '餐饮', shopping: '购物', entertainment: '娱乐' }
    return map[cat] || cat
  }
})
