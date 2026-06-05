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
    apiBase: 'http://127.0.0.1:8000',
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

  // 检查登录状态 → GET /api/auth/me
  checkLogin() {
    const that = this
    wx.request({
      url: `${this.globalData.apiBase}/api/auth/me`,
      header: { Authorization: `Bearer ${this.globalData.token}` },
      success(res) {
        if (res.data && res.data.id) {
          that.globalData.userInfo = res.data
          that.globalData.phoneNumber = res.data.phone || ''
        } else {
          that.globalData.token = ''
          wx.removeStorageSync('token')
        }
      },
      fail() {}
    })
  },

  // 微信登录（小程序授权后调后端换取token）
  // 后端支持 POST /api/auth/login (username/password) 和 POST /api/auth/register
  // 如需微信登录，需后端扩展 /api/auth/wx-login 接口
  wxLogin(callback) {
    const that = this
    wx.login({
      success(loginRes) {
        if (loginRes.code) {
          // 尝试用微信code登录（如果后端支持wx-login）
          wx.request({
            url: `${that.globalData.apiBase}/api/auth/wx-login`,
            method: 'POST',
            data: { code: loginRes.code },
            success(res) {
              if (res.data && res.data.access_token) {
                that.globalData.token = res.data.access_token
                wx.setStorageSync('token', res.data.access_token)
                if (res.data.nickname) {
                  that.globalData.userInfo = { nickname: res.data.nickname }
                }
                callback && callback(true)
              } else {
                // 降级：尝试游客模式注册
                that._guestRegister(callback)
              }
            },
            fail() {
              that._guestRegister(callback)
            }
          })
        }
      }
    })
  },

  // 游客模式兜底登录
  _guestRegister(callback) {
    const that = this
    const guestUser = 'guest_' + Date.now()
    wx.request({
      url: `${this.globalData.apiBase}/api/auth/register`,
      method: 'POST',
      data: {
        username: guestUser,
        password: 'guest123',
        nickname: '游客' + Date.now().toString(36)
      },
      success(res) {
        if (res.data && res.data.access_token) {
          that.globalData.token = res.data.access_token
          wx.setStorageSync('token', res.data.access_token)
          that.globalData.userInfo = { nickname: '游客' }
          callback && callback(true)
        } else {
          callback && callback(false)
        }
      },
      fail() {
        callback && callback(false)
      }
    })
  },

  getPhoneNumber(e, callback) {
    // 后端暂无 bind-phone 接口，预留
    wx.showToast({ title: '手机绑定功能开发中', icon: 'none' })
    callback && callback(false)
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
          } else if (res.data && (res.data.code === 0 || res.data.code === 200)) {
            resolve(res.data.data !== undefined ? res.data.data : res.data)
          } else if (res.data && res.data.id !== undefined) {
            // 直接返回对象（如 /api/auth/me）
            resolve(res.data)
          } else if (res.data && res.data.access_token) {
            // 登录响应
            resolve(res.data)
          } else {
            const msg = (res.data && res.data.msg) || (res.data && res.data.detail) || '请求失败'
            wx.showToast({ title: msg, icon: 'none' })
            reject(res.data || res)
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
