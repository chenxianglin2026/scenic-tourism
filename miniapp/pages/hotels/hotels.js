/**
 * 客房页 - 房型展示 + 预订 + 订单
 */
const api = require('../../utils/api')
const { ROOM_STATUS } = require('../../utils/const')

Page({
  data: {
    // 房型列表
    roomTypes: [],
    // 当前选择
    selectedRoom: null,
    // 预订参数
    checkInDate: '',
    checkOutDate: '',
    guestCount: 1,
    guestName: '',
    guestPhone: '',
    // 订单列表
    orders: [],
    // 视图: 'list' | 'detail' | 'order' | 'orders'
    viewMode: 'list',
    currentOrder: null,
    // 筛选
    statusFilter: '',
    loading: true,
    loadingOrders: false
  },

  onLoad() {
    const today = new Date()
    const tomorrow = new Date(today.getTime() + 86400000)
    const fmt = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
    this.setData({
      checkInDate: fmt(today),
      checkOutDate: fmt(tomorrow)
    })
    this.loadRooms()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
  },

  // 加载房型
  async loadRooms() {
    try {
      const rooms = await api.get('/api/hotels/rooms')
      this.setData({ roomTypes: rooms, loading: false })
    } catch (err) {
      this.setData({
        roomTypes: [
          { id: 1, name: '标准双人房', price: 388, bed_type: '双床', area: '28㎡', capacity: 2, status: 'available', image: '', desc: '舒适双床房，配独立卫浴' },
          { id: 2, name: '豪华大床房', price: 588, bed_type: '大床', area: '35㎡', capacity: 2, status: 'available', image: '', desc: '豪华大床，园景阳台' },
          { id: 3, name: '亲子家庭房', price: 888, bed_type: '双床+儿童床', area: '45㎡', capacity: 4, status: 'booked', image: '', desc: '亲子空间，儿童友好' },
          { id: 4, name: '湖景套房', price: 1288, bed_type: '大床', area: '60㎡', capacity: 2, status: 'available', image: '', desc: '湖景套房，观景阳台' },
          { id: 5, name: '经济单人间', price: 258, bed_type: '单床', area: '20㎡', capacity: 1, status: 'maintenance', image: '', desc: '经济实惠，配套齐全' }
        ],
        loading: false
      })
    }
  },

  // 加载订单
  async loadOrders() {
    this.setData({ loadingOrders: true })
    try {
      const orders = await api.get('/api/hotels/orders', { status: this.data.statusFilter })
      this.setData({ orders, loadingOrders: false })
    } catch (err) {
      this.setData({
        orders: [
          { id: 1, order_no: 'HT20260601001', room_name: '标准双人房', check_in: '2026-06-02', check_out: '2026-06-03', amount: 388, status: 'paid', guest_name: '张三' },
          { id: 2, order_no: 'HT20260601002', room_name: '湖景套房', check_in: '2026-06-05', check_out: '2026-06-07', amount: 2576, status: 'paid', guest_name: '李四' }
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
    this.setData({ selectedRoom: room, viewMode: 'detail' })
  },

  // 返回列表
  onBackToList() {
    this.setData({ viewMode: 'list', selectedRoom: null, currentOrder: null })
  },

  // 查看订单列表
  onViewOrders() {
    this.setData({ viewMode: 'orders' })
    this.loadOrders()
  },

  // 日期选择
  onCheckInChange(e) {
    this.setData({ checkInDate: e.detail.value })
  },

  onCheckOutChange(e) {
    this.setData({ checkOutDate: e.detail.value })
  },

  // 提交预订
  async onBookRoom() {
    const { selectedRoom, checkInDate, checkOutDate, guestName, guestPhone, guestCount } = this.data

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

    // 计算天数
    const d1 = new Date(checkInDate)
    const d2 = new Date(checkOutDate)
    const nights = Math.ceil((d2 - d1) / 86400000) || 1
    const totalAmount = selectedRoom.price * nights

    wx.showLoading({ title: '提交中...' })

    try {
      const order = await api.post('/api/hotels/orders', {
        room_id: selectedRoom.id,
        check_in: checkInDate,
        check_out: checkOutDate,
        guest_name: guestName,
        guest_phone: guestPhone,
        guest_count: guestCount,
        amount: totalAmount
      })
      wx.hideLoading()
      this.setData({ currentOrder: order, viewMode: 'order' })
    } catch (err) {
      wx.hideLoading()
      const mockOrder = {
        id: Date.now(),
        order_no: 'HT' + Date.now(),
        room_name: selectedRoom.name,
        check_in: checkInDate,
        check_out: checkOutDate,
        amount: totalAmount,
        status: 'unpaid',
        guest_name: guestName,
        create_time: new Date().toISOString()
      }
      this.setData({ currentOrder: mockOrder, viewMode: 'order' })
    }
  },

  // 支付（mock）
  onPayOrder() {
    wx.showLoading({ title: '支付中...' })
    setTimeout(() => {
      wx.hideLoading()
      const order = { ...this.data.currentOrder, status: 'paid' }
      this.setData({ currentOrder: order })
      wx.showToast({ title: '预订成功！', icon: 'success' })
    }, 1500)
  },

  // 输入处理
  onGuestNameInput(e) {
    this.setData({ guestName: e.detail.value })
  },

  onGuestPhoneInput(e) {
    this.setData({ guestPhone: e.detail.value })
  },

  onGuestCountChange(e) {
    const { type } = e.currentTarget.dataset
    let count = this.data.guestCount
    if (type === 'plus' && count < 10) count++
    if (type === 'minus' && count > 1) count--
    this.setData({ guestCount: count })
  }
})
