/**
 * 停车缴费页
 * 对接后端: GET /api/parking/rates, POST /api/parking/checkin,
 *           POST /api/parking/checkout/{record_id}, GET /api/parking/records
 */
const api = require('../../utils/api')

Page({
  data: {
    // 停车场列表
    parkingLots: [],
    // 当前选中的停车场
    selectedLot: null,
    // 车牌号
    plateNumber: '',
    // 当前停车记录
    currentRecord: null,
    // 停车记录列表
    records: [],
    // 视图: 'home' | 'active' | 'history'
    viewMode: 'home',
    // 计时器
    timer: null,
    elapsed: '00:00:00',
    loading: true,
    submitting: false
  },

  onLoad() {
    this.loadParkingLots()
    this.loadRecords()
  },

  onUnload() {
    if (this.data.timer) clearInterval(this.data.timer)
  },

  // 加载停车场费率 → GET /api/parking/rates
  async loadParkingLots() {
    try {
      const lots = await api.get('/api/parking/rates')
      const list = (Array.isArray(lots) ? lots : (lots.items || [])).map(lot => ({
        id: lot.id,
        name: lot.name || '停车场',
        vehicleType: lot.vehicle_type || 'car',
        firstHourPrice: lot.first_hour_price || 5,
        additionalHourPrice: lot.additional_hour_price || 3,
        dailyCap: lot.daily_cap || 30,
        freeMinutes: lot.free_minutes || 15,
        totalSpots: lot.total_spots || 0,
        availableSpots: lot.available_spots || 0,
        openTime: lot.open_time || '06:00',
        closeTime: lot.close_time || '20:00'
      }))
      this.setData({ parkingLots: list, loading: false })
    } catch (err) {
      this.setData({
        parkingLots: [
          { id: 1, name: '红门停车场（小客车）', vehicleType: 'car', firstHourPrice: 5, additionalHourPrice: 3, dailyCap: 30, freeMinutes: 15, totalSpots: 500, availableSpots: 350, openTime: '06:00', closeTime: '20:00' },
          { id: 2, name: '天外村停车场（小客车）', vehicleType: 'car', firstHourPrice: 5, additionalHourPrice: 3, dailyCap: 30, freeMinutes: 15, totalSpots: 300, availableSpots: 180, openTime: '06:00', closeTime: '20:00' },
          { id: 3, name: '红门停车场（大巴）', vehicleType: 'bus', firstHourPrice: 10, additionalHourPrice: 6, dailyCap: 60, freeMinutes: 30, totalSpots: 50, availableSpots: 35, openTime: '06:00', closeTime: '20:00' }
        ],
        loading: false
      })
    }
  },

  // 加载停车记录 → GET /api/parking/records
  async loadRecords() {
    try {
      const data = await api.get('/api/parking/records')
      const records = (Array.isArray(data) ? data : (data.items || [])).map(r => ({
        id: r.id,
        plateNumber: r.plate_number || '',
        lotName: r.parking_name || '',
        checkinTime: r.checkin_time || '',
        checkoutTime: r.checkout_time || '',
        duration: r.duration_minutes || 0,
        fee: r.total_fee || 0,
        status: r.status || 'active'
      }))
      this.setData({ records })
    } catch (err) {
      this.setData({ records: [] })
    }
  },

  // 选择停车场
  onSelectLot(e) {
    const { id } = e.currentTarget.dataset
    const lot = this.data.parkingLots.find(l => l.id == id)
    this.setData({ selectedLot: lot })
  },

  // 输入车牌号
  onPlateInput(e) {
    this.setData({ plateNumber: e.detail.value.toUpperCase() })
  },

  // 快捷省份选择
  onProvinceTap(e) {
    const { province } = e.currentTarget.dataset
    this.setData({ plateNumber: province })
  },

  // 车辆进场 → POST /api/parking/checkin
  async onCheckin() {
    if (this.data.submitting) return
    const { selectedLot, plateNumber } = this.data

    if (!selectedLot) {
      wx.showToast({ title: '请选择停车场', icon: 'none' })
      return
    }
    if (!plateNumber) {
      wx.showToast({ title: '请输入车牌号', icon: 'none' })
      return
    }

    // 检查车牌格式
    if (!/^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁][A-Z][A-Z0-9]{4,6}$/.test(plateNumber)) {
      wx.showToast({ title: '车牌号格式不正确', icon: 'none' })
      return
    }

    wx.showLoading({ title: '登记中...' })
    this.setData({ submitting: true })

    try {
      const record = await api.post('/api/parking/checkin', {
        rate_id: selectedLot.id,
        plate_number: plateNumber
      })
      wx.hideLoading()

      const currentRecord = {
        id: record.id,
        plateNumber: record.plate_number || plateNumber,
        lotName: record.lot_name || selectedLot.name,
        checkinTime: record.checkin_time || new Date().toISOString(),
        lotId: selectedLot.id
      }

      this.setData({ currentRecord, viewMode: 'active', submitting: false })
      this.startTimer()
      wx.showToast({ title: '登记成功', icon: 'success' })
    } catch (err) {
      wx.hideLoading()
      // mock降级
      const now = new Date().toISOString()
      this.setData({
        currentRecord: {
          id: Date.now(),
          plateNumber,
          lotName: selectedLot.name,
          checkinTime: now,
          lotId: selectedLot.id
        },
        viewMode: 'active',
        submitting: false
      })
      this.startTimer()
      wx.showToast({ title: '登记成功(模拟)', icon: 'success' })
    }
  },

  // 车辆出场 → POST /api/parking/checkout/{record_id}
  async onCheckout() {
    const { currentRecord, selectedLot } = this.data

    wx.showModal({
      title: '确认离场',
      content: `车牌 ${currentRecord.plateNumber}\n停车时长: ${this.data.elapsed}\n\n确认离场并缴费？`,
      confirmText: '确认离场',
      success: async (res) => {
        if (!res.confirm) return

        wx.showLoading({ title: '结算中...' })

        try {
          const result = await api.post(`/api/parking/checkout/${currentRecord.id}`)
          wx.hideLoading()

          // 显示缴费结果
          const fee = result.total_fee || 0
          wx.showModal({
            title: '缴费完成',
            content: `车牌: ${currentRecord.plateNumber}\n停车场: ${currentRecord.lotName}\n停车时长: ${this.data.elapsed}\n费用: ¥${fee.toFixed(2)}`,
            showCancel: false,
            confirmText: '好的',
            success: () => {
              this.stopTimer()
              this.setData({ currentRecord: null, viewMode: 'home' })
              this.loadRecords()
            }
          })
        } catch (err) {
          wx.hideLoading()
          // mock降级 - 计算费用
          const fee = this.calcMockFee()
          wx.showModal({
            title: '缴费完成(模拟)',
            content: `车牌: ${currentRecord.plateNumber}\n停车场: ${currentRecord.lotName}\n停车时长: ${this.data.elapsed}\n费用: ¥${fee.toFixed(2)}`,
            showCancel: false,
            confirmText: '好的',
            success: () => {
              this.stopTimer()
              this.setData({ currentRecord: null, viewMode: 'home' })
              // 添加到本地记录
              const records = this.data.records
              records.unshift({
                id: Date.now(),
                plateNumber: currentRecord.plateNumber,
                lotName: currentRecord.lotName,
                checkinTime: currentRecord.checkinTime,
                checkoutTime: new Date().toISOString(),
                fee,
                status: 'completed'
              })
              this.setData({ records })
            }
          })
        }
      }
    })
  },

  // 启动计时器
  startTimer() {
    const checkinTime = new Date(this.data.currentRecord.checkinTime).getTime()
    const timer = setInterval(() => {
      const diff = Math.floor((Date.now() - checkinTime) / 1000)
      const h = Math.floor(diff / 3600)
      const m = Math.floor((diff % 3600) / 60)
      const s = diff % 60
      this.setData({
        elapsed: `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
      })
    }, 1000)
    this.setData({ timer })
  },

  // 停止计时器
  stopTimer() {
    if (this.data.timer) {
      clearInterval(this.data.timer)
      this.setData({ timer: null, elapsed: '00:00:00' })
    }
  },

  // 计算模拟费用
  calcMockFee() {
    const checkinTime = new Date(this.data.currentRecord.checkinTime).getTime()
    const diffMinutes = Math.floor((Date.now() - checkinTime) / 60000)
    const { selectedLot } = this.data

    if (!selectedLot) return 0

    // 15分钟内免费
    if (diffMinutes <= selectedLot.freeMinutes) return 0

    const chargeMinutes = diffMinutes - selectedLot.freeMinutes
    const hours = Math.ceil(chargeMinutes / 60)
    let fee = 0
    if (hours <= 1) {
      fee = selectedLot.firstHourPrice
    } else {
      fee = selectedLot.firstHourPrice + (hours - 1) * selectedLot.additionalHourPrice
    }
    // 日封顶
    if (fee > selectedLot.dailyCap) fee = selectedLot.dailyCap

    return fee
  },

  // 查看记录详情
  onRecordTap(e) {
    const { id } = e.currentTarget.dataset
    const record = this.data.records.find(r => r.id == id)
    if (record) {
      const status = record.status === 'active' ? '进行中' : '已完成'
      wx.showModal({
        title: '停车记录',
        content: `车牌: ${record.plateNumber}\n停车场: ${record.lotName}\n进场: ${record.checkinTime?.slice(0, 19) || '--'}\n${record.checkoutTime ? '离场: ' + record.checkoutTime.slice(0, 19) : ''}\n费用: ¥${(record.fee || 0).toFixed(2)}\n状态: ${status}`,
        showCancel: false,
        confirmText: '关闭'
      })
    }
  },

  // 返回首页
  onBackHome() {
    this.stopTimer()
    this.setData({ viewMode: 'home', currentRecord: null })
    this.loadRecords()
  }
})
