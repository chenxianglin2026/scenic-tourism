/**
 * 景区介绍 + 导览地图
 * 对接后端: GET /api/scenic/info, GET /api/scenic/pois
 */
const api = require('../../utils/api')

Page({
  data: {
    scenic: {},
    pois: [],
    poiCategories: [],
    activeCategory: 'all',
    loading: true,
    // POI 分类图标映射
    categoryIcons: {
      entrance: '🚪',
      viewpoint: '🏔️',
      service: 'ℹ️',
      restaurant: '🍽️',
      shop: '🛍️',
      toilet: '🚻',
      parking: '🅿️',
      other: '📍'
    }
  },

  onLoad() {
    this.loadAll()
  },

  async loadAll() {
    wx.showLoading({ title: '加载中...' })
    try {
      await Promise.all([this.loadScenicInfo(), this.loadPOIs()])
    } finally {
      wx.hideLoading()
      this.setData({ loading: false })
    }
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
        openTime: data.open_time || '06:00',
        closeTime: data.close_time || '18:00',
        rating: data.rating || 4.8,
        cover_image: data.cover_image || '',
        lat: data.lat || 36.25,
        lng: data.lng || 117.125,
        city: data.city || '',
        district: data.district || ''
      }
      this.setData({ scenic })
    } catch (err) {
      const app = getApp()
      this.setData({
        scenic: {
          ...app.globalData.currentScenic,
          openTime: '06:00',
          closeTime: '18:00',
          rating: 4.8
        }
      })
    }
  },

  // 加载POI点位 → GET /api/scenic/pois
  async loadPOIs() {
    try {
      const spotId = (getApp().globalData.currentScenic || {}).id || 1
      const pois = await api.get('/api/scenic/pois', { spot_id: spotId })
      const list = (Array.isArray(pois) ? pois : (pois.items || []))

      // 提取分类列表
      const catSet = new Set()
      list.forEach(p => catSet.add(p.category || 'other'))

      const categories = ['all', ...catSet]
      this.setData({
        pois: list,
        poiCategories: categories.map(c => ({
          key: c,
          label: this._categoryLabel(c),
          icon: this.data.categoryIcons[c] || '📍'
        }))
      })
    } catch (err) {
      // mock 降级
      this.setData({
        pois: [
          { id: 1, name: '红门入口', category: 'entrance', description: '传统登山入口', lat: 36.211, lng: 117.128 },
          { id: 2, name: '天外村入口', category: 'entrance', description: '景区大巴入口', lat: 36.206, lng: 117.11 },
          { id: 3, name: '中天门', category: 'viewpoint', description: '半山腰，索道和徒步交汇处', lat: 36.235, lng: 117.12 },
          { id: 4, name: '南天门', category: 'viewpoint', description: '泰山标志性建筑', lat: 36.25, lng: 117.125 },
          { id: 5, name: '玉皇顶', category: 'viewpoint', description: '主峰，海拔1545米', lat: 36.258, lng: 117.125 },
          { id: 6, name: '碧霞祠', category: 'viewpoint', description: '供奉碧霞元君', lat: 36.253, lng: 117.124 },
          { id: 7, name: '日观峰', category: 'viewpoint', description: '观赏日出最佳地点', lat: 36.255, lng: 117.127 },
          { id: 8, name: '红门游客中心', category: 'service', description: '咨询/寄存/医疗', lat: 36.2115, lng: 117.1275 },
          { id: 9, name: '中天门餐厅', category: 'restaurant', description: '泰山特色美食', lat: 36.2355, lng: 117.1205 },
          { id: 10, name: '天街商店', category: 'shop', description: '纪念品商店', lat: 36.251, lng: 117.1255 }
        ],
        poiCategories: [
          { key: 'all', label: '全部', icon: '📍' },
          { key: 'entrance', label: '入口', icon: '🚪' },
          { key: 'viewpoint', label: '景点', icon: '🏔️' },
          { key: 'service', label: '服务', icon: 'ℹ️' },
          { key: 'restaurant', label: '餐饮', icon: '🍽️' },
          { key: 'shop', label: '商店', icon: '🛍️' }
        ]
      })
    }
  },

  _categoryLabel(cat) {
    const map = {
      entrance: '入口',
      viewpoint: '景点',
      service: '服务',
      restaurant: '餐饮',
      shop: '商店',
      toilet: '卫生间',
      parking: '停车场',
      all: '全部'
    }
    return map[cat] || cat
  },

  // 切换分类
  onCategoryTap(e) {
    const { key } = e.currentTarget.dataset
    this.setData({ activeCategory: key })
  },

  // 查看POI详情
  onPoiTap(e) {
    const { id } = e.currentTarget.dataset
    const poi = this.data.pois.find(p => p.id == id)
    if (poi) {
      wx.showModal({
        title: poi.name,
        content: `${poi.description || '暂无描述'}\n\n坐标: ${(poi.lat||0).toFixed(4)}, ${(poi.lng||0).toFixed(4)}`,
        showCancel: false,
        confirmText: '知道了'
      })
    }
  },

  // 拨打电话
  onCall() {
    const phone = this.data.scenic.phone
    if (phone) {
      wx.makePhoneCall({ phoneNumber: phone })
    } else {
      wx.showToast({ title: '暂无联系电话', icon: 'none' })
    }
  },

  // 导航到景区
  onNavigate() {
    const { lat, lng, name, address } = this.data.scenic
    wx.openLocation({
      latitude: lat || 36.25,
      longitude: lng || 117.125,
      name: name || '泰山风景名胜区',
      address: address || '',
      scale: 14
    })
  }
})
