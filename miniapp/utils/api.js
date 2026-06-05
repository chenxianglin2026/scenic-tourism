/**
 * 景区智慧管理系统小程序 - API 封装
 * BaseURL: 后端服务地址
 * 封装 wx.request，统一请求/响应拦截、Token 管理、错误处理
 */

const { DEV_MODE } = require('./const')
const BASE_URL = 'http://43.163.5.90:8001'

let isRefreshing = false
let refreshQueue = []

const getDefaultHeader = () => {
  const header = { 'Content-Type': 'application/json' }
  const token = wx.getStorageSync('token')
  if (token) {
    header['Authorization'] = `Bearer ${token}`
  }
  return header
}

const request = (options) => {
  return new Promise((resolve, reject) => {
    const {
      url,
      method = 'GET',
      data = {},
      header: customHeader = {},
      showLoading = false,
      loadingText = '加载中...',
      timeout = 30000
    } = options

    if (showLoading) {
      wx.showLoading({ title: loadingText, mask: true })
    }

    const mergedHeader = { ...getDefaultHeader(), ...customHeader }
    const requestUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`

    if (DEV_MODE) console.log(`[API] ${method} ${requestUrl}`, data)

    wx.request({
      url: requestUrl,
      method,
      data,
      header: mergedHeader,
      timeout,
      success(res) {
        if (showLoading) wx.hideLoading()
        const { statusCode, data: resData } = res
        if (DEV_MODE) console.log(`[API] Response ${statusCode}:`, resData)

        switch (statusCode) {
          case 200:
          case 201:
          case 204:
            if (resData && resData.code !== undefined) {
              if (resData.code === 0 || resData.code === 200) {
                resolve(resData.data !== undefined ? resData.data : resData)
              } else if (resData.code === 401) {
                handleAuthExpired()
                reject({ code: 401, msg: resData.msg || '登录已过期' })
              } else {
                wx.showToast({ title: resData.msg || '请求失败', icon: 'none' })
                reject(resData)
              }
            } else {
              resolve(resData)
            }
            break
          case 401:
            handleAuthExpired()
            reject({ code: 401, msg: '未授权，请重新登录' })
            break
          case 403:
            wx.showToast({ title: '没有权限', icon: 'none' })
            reject({ code: 403, msg: '没有权限' })
            break
          case 404:
            wx.showToast({ title: '请求的资源不存在', icon: 'none' })
            reject({ code: 404, msg: '资源不存在' })
            break
          case 500:
            wx.showToast({ title: '服务器繁忙，请稍后重试', icon: 'none' })
            reject({ code: 500, msg: '服务器错误' })
            break
          default:
            wx.showToast({ title: `请求失败(${statusCode})`, icon: 'none' })
            reject({ code: statusCode, msg: '请求失败' })
        }
      },
      fail(err) {
        if (showLoading) wx.hideLoading()
        if (DEV_MODE) console.error('[API] Network error:', err)
        wx.showToast({ title: '网络异常，请检查网络', icon: 'none' })
        reject({ code: -1, msg: '网络异常', error: err })
      }
    })
  })
}

const handleAuthExpired = () => {
  wx.removeStorageSync('token')
  const app = getApp()
  if (app) {
    app.globalData.token = ''
    app.globalData.userInfo = null
  }
  wx.switchTab({ url: '/pages/mine/mine' })
}

const api = {
  get(url, data = {}, options = {}) {
    return request({ url, method: 'GET', data, ...options })
  },

  post(url, data = {}, options = {}) {
    return request({ url, method: 'POST', data, ...options })
  },

  put(url, data = {}, options = {}) {
    return request({ url, method: 'PUT', data, ...options })
  },

  delete(url, data = {}, options = {}) {
    return request({ url, method: 'DELETE', data, ...options })
  },

  upload(url, filePath, name = 'file', formData = {}) {
    return new Promise((resolve, reject) => {
      const token = wx.getStorageSync('token')
      const header = token ? { 'Authorization': `Bearer ${token}` } : {}
      const uploadUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`

      wx.showLoading({ title: '上传中...', mask: true })

      wx.uploadFile({
        url: uploadUrl,
        filePath,
        name,
        formData,
        header,
        success(res) {
          wx.hideLoading()
          try {
            const data = JSON.parse(res.data)
            if (data.code === 0 || data.code === 200) {
              resolve(data.data !== undefined ? data.data : data)
            } else {
              wx.showToast({ title: data.msg || '上传失败', icon: 'none' })
              reject(data)
            }
          } catch (e) {
            resolve(res.data)
          }
        },
        fail(err) {
          wx.hideLoading()
          wx.showToast({ title: '上传失败', icon: 'none' })
          reject(err)
        }
      })
    })
  }
}

module.exports = api
