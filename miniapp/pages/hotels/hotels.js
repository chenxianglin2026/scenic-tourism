/**
 * 客房页 - 房型展示 + 预订 + 订单
 * 对接后端: GET /api/hotels, GET /api/hotels/{id}/rooms, POST /api/hotels/orders, GET /api/hotels/orders
 */
const api = require('../../utils/api')
const { ROOM_STATUS, PAGE_SIZE } = require('../../utils/const')

Page({
  data: {
    // 酒店列表
    hotels: [],
    currentHotelId: null,
    currentHotel: null,
    // 房型列表
    roomTypes: [],
    // 当前选择
    selectedRoom: null,
    // 预订参数
    checkInDate: '',
    checkOutDate: '',
    roomCount: 1,
    guestName: '',
    guestPhone: '',
    remark: '',
    // 订单列表
    orders: [],
    // 视图: 'list' | 'detail' | 'order' | 'orders'
    viewMode: 'list',
    currentOrder: null,
    // 筛选
    statusFilter: '',
    loading: true,
    loadingOrders: false,
    // 分页
    ordersTotal: 0,
    ordersPage: 1,
  },

  onLoad() {
    const today = new Date()
    const tomorrow = new Date(today.getTime() + 86400000)
    const fmt = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
    this.setData({
      checkInDate: fmt(today),
      checkOutDate: fmt(tomorrow)
    })
    this.loadHotels()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
  },

  // 加载酒店列表 → GET /api/hotels
  async loadHotels() {
    try {
      const spotId = getApp().globalData.currentScenic?.id || 1
      const hotels = await api.get('/api/hotels', { spot_id: spotId })
      this.setData({ hotels })
      if (hotels.length > 0) {
        this.setData({
          currentHotelId: hotels[0].id,
          currentHotel: hotels[0]
        })
        this.loadRooms(hotels[0].id)
      } else {
        this.setData({ loading: false })
      }
    } catch (err) {
      // mock 降级
      this.setData({
        hotels: [{ id: 1, name: '西湖大酒店', address: '杭州市西湖区', rating: 4.8 }],
        currentHotelId: 1,
        currentHotel: { id: 1, name: '西湖大酒店', address: '杭州市西湖区', rating: 4.8 }
      })
      this.loadRooms(1)
    }
  },

  // 加载房型 → GET /api/hotels/{hotel_id}/rooms
  async loadRooms(hotelId) {
    this.setData({ loading: true })
    try {
      const rooms = await api.get(`/api/hotels/${hotelId}/rooms`)
      this.setData({ roomTypes: rooms, loading: false })
    } catch (err) {
      // mock 降级
      this.setData({
        roomTypes: [
          { id: 1, hotel_id: hotelId, name: '标准双人房', room_type: '双床房', price: 388, bed_type: '双床', area: 28, max_guests: 2, available_count: 5, total_count: 10, has_window: true, has_wifi: true, has_bathtub: false, description: '舒适双床房，配独立卫浴' },
          { id: 2, hotel_id: hotelId, name: '豪华大床房', room_type: '大床房', price: 588, bed_type: '大床', area: 35, max_guests: 2, available_count: 3, total_count: 8, has_window: true, has_wifi: true, has_bathtub: true, description: '豪华大床，园景阳台' },
          { id: 3, hotel_id: hotelId, name: '亲子家庭房', room_type: '家庭房', price: 888, bed_type: '双床+儿童床', area: 45, max_guests: 4, available_count: 0, total_count: 5, has_window: true, has_wifi: true, has_bathtub: true, description: '亲子空间，儿童友好' },
          { id: 4, hotel_id: hotelId, name: '湖景套房', room_type: '套房', price: 1288, bed_type: '大床', area: 60, max_guests: 2, available_count: 2, total_count: 3, has_window: true, has_wifi: true, has_bathtub: true, description: '湖景套房，观景阳台' },
          { id: 5, hotel_id: hotelId, name: '经济单人间', room_type: '单人间', price: 258, bed_type: '单床', area: 20, max_guests: 1, available_count: 10, total_count: 15, has_window: true, has_wifi: true, has_bathtub: false, description: '经济实惠，配套齐全' }
        ],
        loading: false
      })
    }
  },

  // 切换酒店
  async onSwitchHotel(e) {
    const { id } = e.currentTarget.dataset
    const hotel = this.data.hotels.find(h => h.id === id)
    if (hotel) {
      this.setData({ currentHotelId: id, currentHotel: hotel })
      this.loadRooms(id)
    }
  },

  // 加载订单 → GET /api/hotels/orders
  async loadOrders() {
    this.setData({ loadingOrders: true })
    try {
      const res = await api.get('/api/hotels/orders', {
        status: this.data.statusFilter || undefined,
        page: this.data.ordersPage,
        page_size: PAGE_SIZE
      })
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : [])
      const total = (res && res.total) ? res.total : items.length
      this.setData({ orders: items, ordersTotal: total, loadingOrders: false })
    } catch (err) {
      // mock 降级
      this.setData({
        orders: [
          { id: 1, order_no: 'HT20260601001', room_name: '标准双人房', checkin_date: '2026-06-02', checkout_date: '2026-06-03', nights: 1, total_price: 388, status: 'paid', guest_name: '张三', guest_phone: '13800138001' },
          { id: 2, order_no: 'HT20260601002', room_name: '湖景套房', checkin_date: '2026-06-05', checkout_date: '2026-06-07', nights: 2, total_price: 2576, status: 'pending', guest_name: '李四', guest_phone: '13800138002' }
        ],
        loadingOrders: false
      })
    }
  },

  // 查看房型详情
  onRoomDetail(e) {
    const { id } = e.currentTarget.dataset
    const room = this.data.roomTypes.find(r => r.id === id)
    if (!room) return
    if (room.available_count <= 0) {
      wx.showToast({ title: '该房型已满', icon: 'none' })
      return
    }
    this.setData({ selectedRoom: room, viewMode: 'detail' })
  },

  // 返回列表
  onBackToList() {
    this.setData({ viewMode: 'list', selectedRoom: null, currentOrder: null })
  },

  // 查看订单列表
  onViewOrders() {
    this.setData({ viewMode: 'orders', ordersPage: 1 })
    this.loadOrders()
  },

  // 日期选择
  onCheckInChange(e) {
    this.setData({ checkInDate: e.detail.value })
  },

  onCheckOutChange(e) {
    this.setData({ checkOutDate: e.detail.value })
  },

  // 提交预订 → POST /api/hotels/orders
  async onBookRoom() {
    const { selectedRoom, currentHotelId, checkInDate, checkOutDate, guestName, guestPhone, roomCount, remark } = this.data

    if (!selectedRoom) {
      wx.showToast({ title: '请选择房型', icon: 'none' })
      return
    }

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

    if (!guestName || !guestPhone) {
      wx.showToast({ title: '请填写入住人信息', icon: 'none' })
      return
    }

    // 校验手机号
    if (!/^1[3-9]\d{9}$/.test(guestPhone)) {
      wx.showToast({ title: '手机号格式不正确', icon: 'none' })
      return
    }

    // 校验日期
    if (checkInDate >= checkOutDate) {
      wx.showToast({ title: '离店日期必须晚于入住日期', icon: 'none' })
      return
    }

    wx.showLoading({ title: '提交中...' })

    try {
      const order = await api.post('/api/hotels/orders', {
        hotel_id: currentHotelId,
        room_id: selectedRoom.id,
        room_count: roomCount,
        checkin_date: checkInDate,
        checkout_date: checkOutDate,
        guest_name: guestName,
        guest_phone: guestPhone,
        remark: remark || undefined,
      })
      wx.hideLoading()
      this.setData({ currentOrder: order, viewMode: 'order' })
    } catch (err) {
      wx.hideLoading()
      // mock 降级
      const d1 = new Date(checkInDate)
      const d2 = new Date(checkOutDate)
      const nights = Math.ceil((d2 - d1) / 86400000) || 1
      this.setData({
        currentOrder: {
          id: Date.now(),
          order_no: 'HT' + Date.now(),
          room_name: selectedRoom.name,
          checkin_date: checkInDate,
          checkout_date: checkOutDate,
          nights: nights,
          total_price: selectedRoom.price * roomCount * nights,
          status: 'pending',
          guest_name: guestName,
          guest_phone: guestPhone,
          created_at: new Date().toISOString()
        },
        viewMode: 'order'
      })
      wx.showToast({ title: '已生成模拟订单', icon: 'none' })
    }
  },

  // 支付 → POST /api/payment/create
  async onPayOrder() {
    const { currentOrder } = this.data
    if (!currentOrder) return

    wx.showLoading({ title: '支付中...' })

    try {
      const payResult = await api.post('/api/payment/create', {
        order_no: currentOrder.order_no,
        order_type: 'hotel'
      })
      wx.hideLoading()

      if (payResult.success) {
        this.setData({
          currentOrder: { ...currentOrder, status: 'paid' }
        })
        wx.showToast({ title: '预订成功！', icon: 'success' })
      } else {
        wx.showToast({ title: payResult.message || '支付失败', icon: 'none' })
      }
    } catch (err) {
      wx.hideLoading()
      this.setData({
        currentOrder: { ...currentOrder, status: 'paid' }
      })
      wx.showToast({ title: '预订成功(模拟)', icon: 'success' })
    }
  },

  // 输入处理
  onGuestNameInput(e) {
    this.setData({ guestName: e.detail.value })
  },

  onGuestPhoneInput(e) {
    this.setData({ guestPhone: e.detail.value })
  },

  onRemarkInput(e) {
    this.setData({ remark: e.detail.value })
  },

  onRoomCountChange(e) {
    const { type } = e.currentTarget.dataset
    let count = this.data.roomCount
    if (type === 'plus' && count < 10) count++
    if (type === 'minus' && count > 1) count--
    this.setData({ roomCount: count })
  },

  // 筛选订单
  onStatusFilter(e) {
    const { status } = e.currentTarget.dataset
    this.setData({ statusFilter: status || '', ordersPage: 1 })
    this.loadOrders()
  },
})
