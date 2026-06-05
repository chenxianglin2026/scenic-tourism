App({
  globalData: {
    token: '',
    userInfo: null,
    phoneNumber: '',
    realName: '',
    idCard: '',
    // 当前景区
    currentScenic: {
      id: 1,
      name: '西湖风景名胜区',
      address: '杭州市西湖区龙井路1号',
      lat: 30.2375,
      lng: 120.1398,
      phone: '0571-88886666',
      openTime: '08:00-17:30',
      description: '杭州西湖，人间天堂'
    },
    // API 基础地址
    apiBase: 'http://127.0.0.1:8001',
    // 当前定位
    location: {
      lat: 30.2375,
      lng: 120.1398,
      city: '杭州'
    }
  },

  onLaunch() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.checkLogin()
    }

    const sys = wx.getSystemInfoSync()
    this.globalData.systemInfo = sys
    this.globalData.statusBarHeight = sys.statusBarHeight
    this.globalData.navBarHeight = sys.platform === 'android' ? 48 : 44
    this.globalData.safeTop = sys.statusBarHeight + (sys.platform === 'android' ? 48 : 44)
  },

  checkLogin() {
    const that = this
    wx.request({
      url: `${this.globalData.apiBase}/api/user/profile`,
      header: { Authorization: `Bearer ${this.globalData.token}` },
      success(res) {
        if (res.data.code === 0) {
          that.globalData.userInfo = res.data.data
        } else {
          that.globalData.token = ''
          wx.removeStorageSync('token')
        }
      },
      fail() {}
    })
  },

  wxLogin(callback) {
    const that = this
    wx.login({
      success(loginRes) {
        if (loginRes.code) {
          wx.request({
            url: `${that.globalData.apiBase}/api/auth/wx-login`,
            method: 'POST',
            data: { code: loginRes.code },
            success(res) {
              if (res.data.code === 0 && res.data.data.token) {
                that.globalData.token = res.data.data.token
                wx.setStorageSync('token', res.data.data.token)
                if (res.data.data.userInfo) {
                  that.globalData.userInfo = res.data.data.userInfo
                }
                callback && callback(true)
              } else {
                callback && callback(false)
              }
            },
            fail() {
              callback && callback(false)
            }
          })
        }
      }
    })
  },

  getPhoneNumber(e, callback) {
    const that = this
    if (e.detail.errMsg !== 'getPhoneNumber:ok') {
      wx.showToast({ title: '获取手机号失败', icon: 'none' })
      return
    }
    wx.request({
      url: `${this.globalData.apiBase}/api/auth/bind-phone`,
      method: 'POST',
      header: { Authorization: `Bearer ${this.globalData.token}` },
      data: {
        encryptedData: e.detail.encryptedData,
        iv: e.detail.iv
      },
      success(res) {
        if (res.data.code === 0) {
          that.globalData.phoneNumber = res.data.data.phone
          callback && callback(true, res.data.data.phone)
        } else {
          wx.showToast({ title: '绑定失败', icon: 'none' })
          callback && callback(false)
        }
      }
    })
  },

  request(options) {
    const app = this
    return new Promise((resolve, reject) => {
      const header = { 'Content-Type': 'application/json' }
      if (app.globalData.token) {
        header.Authorization = `Bearer ${app.globalData.token}`
      }
      wx.request({
        url: `${app.globalData.apiBase}${options.url}`,
        method: options.method || 'GET',
        data: options.data || {},
        header,
        success(res) {
          if (res.statusCode === 401) {
            app.globalData.token = ''
            wx.removeStorageSync('token')
            wx.navigateTo({ url: '/pages/mine/mine' })
            reject(res)
          } else if (res.data.code === 0) {
            resolve(res.data.data)
          } else {
            wx.showToast({ title: res.data.msg || '请求失败', icon: 'none' })
            reject(res.data)
          }
        },
        fail(err) {
          wx.showToast({ title: '网络异常', icon: 'none' })
          reject(err)
        }
      })
    })
  }
})
