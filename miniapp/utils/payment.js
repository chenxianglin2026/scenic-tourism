/**
 * 微信支付工具模块
 * 流程: 调后端 /api/payment/create 获取支付参数 → wx.requestPayment 拉起支付
 */

const api = require('./api')

/**
 * 发起微信支付
 * @param {Object} params
 * @param {string} params.orderNo    - 订单号
 * @param {string} params.orderType  - 订单类型: 'ticket' | 'hotel'
 * @param {number} params.totalFee   - 金额(分)，仅作展示
 * @param {string} params.desc       - 商品描述
 * @returns {Promise<Object>} 支付成功 resolve({orderNo}), 失败 reject
 */
function requestPayment({ orderNo, orderType = 'ticket', totalFee = 0, desc = '' }) {
  return new Promise((resolve, reject) => {
    wx.showLoading({ title: '获取支付参数...', mask: true })

    // Step 1: 调后端创建支付订单，获取 wx.requestPayment 所需参数
    api.post('/api/payment/create', {
      order_no: orderNo,
      order_type: orderType,
      total_fee: totalFee,
      description: desc
    }).then(payParams => {
      wx.hideLoading()

      // 后端返回的支付参数通常为:
      // { timeStamp, nonceStr, package, signType, paySign }
      // 部分后端用下划线命名，兼容两种格式
      const paymentData = {
        timeStamp: String(payParams.timeStamp || payParams.timestamp || ''),
        nonceStr:  String(payParams.nonceStr  || payParams.nonce_str  || ''),
        package:   String(payParams.package   || payParams.packageValue || ''),
        signType:  String(payParams.signType  || payParams.sign_type   || 'MD5'),
        paySign:   String(payParams.paySign   || payParams.pay_sign    || ''),
      }

      // 校验必要参数
      if (!paymentData.timeStamp || !paymentData.nonceStr || !paymentData.package || !paymentData.paySign) {
        console.error('[Payment] 支付参数不完整:', paymentData)
        wx.showToast({ title: '支付参数异常，请联系客服', icon: 'none' })
        reject(new Error('支付参数不完整'))
        return
      }

      // Step 2: 拉起微信支付
      wx.requestPayment({
        ...paymentData,
        success(res) {
          console.log('[Payment] 支付成功:', res)
          resolve({ orderNo, raw: res })
        },
        fail(err) {
          console.error('[Payment] 支付失败:', err)
          if (err.errMsg && err.errMsg.indexOf('cancel') === -1) {
            wx.showToast({ title: '支付失败，请重试', icon: 'none' })
          }
          reject(err)
        }
      })
    }).catch(err => {
      wx.hideLoading()
      console.error('[Payment] 获取支付参数失败:', err)
      wx.showToast({ title: '创建支付订单失败', icon: 'none' })
      reject(err)
    })
  })
}

module.exports = { requestPayment }
