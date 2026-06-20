/**
 * 游客评价 - 查看评价 + 发表评价
 * 对接后端: GET /api/scenic/reviews, POST /api/scenic/reviews
 */
const api = require('../../utils/api')

Page({
  data: {
    // 评价列表
    reviews: [],
    avgRating: 0,
    ratingDistribution: {},
    total: 0,
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: false,
    refreshing: false,
    // 筛选
    ratingFilter: 0, // 0=全部, 1-5
    // 发表评价
    showCommentModal: false,
    commentRating: 5,
    commentContent: '',
    commentVisitDate: '',
    submitting: false,
    // 图片展开
    previewImages: [],
    previewVisible: false
  },

  onLoad() {
    this.loadReviews()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true, refreshing: true })
    this.loadReviews().finally(() => {
      wx.stopPullDownRefresh()
      this.setData({ refreshing: false })
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadReviews(true)
    }
  },

  // 加载评价列表 → GET /api/scenic/reviews
  async loadReviews(append = false) {
    if (this.data.loading) return
    this.setData({ loading: true })

    const params = {
      page: append ? this.data.page + 1 : 1,
      page_size: this.data.pageSize
    }
    if (this.data.ratingFilter > 0) {
      params.rating = this.data.ratingFilter
    }

    try {
      const spotId = (getApp().globalData.currentScenic || {}).id
      if (spotId) params.spot_id = spotId

      const res = await api.get('/api/scenic/reviews', params)
      const items = (res && res.items) ? res.items : (Array.isArray(res) ? res : [])
      const total = (res && res.total) ? res.total : items.length
      const avgRating = (res && res.avg_rating !== undefined) ? res.avg_rating : 4.5
      const ratingDistribution = (res && res.rating_distribution) ? res.rating_distribution : {}

      const reviews = append
        ? [...this.data.reviews, ...items]
        : items

      this.setData({
        reviews,
        total,
        avgRating,
        ratingDistribution,
        page: append ? this.data.page + 1 : 1,
        hasMore: reviews.length < total,
        loading: false
      })
    } catch (err) {
      // mock 降级
      this.setData({
        reviews: [
          { id: 1, nickname: '旅行者小王', avatar_url: '', rating: 5, content: '泰山真的太壮观了！日出超级美，不虚此行。建议早点出发，带好水和干粮。', like_count: 128, visit_date: '2026-05-28', created_at: '2026-05-29T10:30:00', images: '' },
          { id: 2, nickname: '登山爱好者', avatar_url: '', rating: 5, content: '第三次爬泰山了，每次都有不同的感受。红门路线经典，沿途风景好。', like_count: 86, visit_date: '2026-05-20', created_at: '2026-05-21T14:20:00' },
          { id: 3, nickname: '家庭出游', avatar_url: '', rating: 4, content: '带了老人和小孩，选择天外村坐大巴到中天门再坐索道，很方便。景区设施完善，服务态度好。', like_count: 52, visit_date: '2026-05-15', created_at: '2026-05-16T09:00:00' },
          { id: 4, nickname: '摄影达人', avatar_url: '', rating: 5, content: '拍到了绝美的日出和云海，泰山果然是摄影师的天堂。推荐日观峰拍摄。', like_count: 203, visit_date: '2026-05-10', created_at: '2026-05-11T16:45:00', images: '' },
          { id: 5, nickname: '游客张三', avatar_url: '', rating: 3, content: '景色不错但是人太多了，排队时间比较长。建议避开节假日。', like_count: 15, visit_date: '2026-05-01', created_at: '2026-05-02T11:00:00' },
          { id: 6, nickname: '文化爱好者', avatar_url: '', rating: 4, content: '历史文化底蕴深厚，石刻很多，建议请个导游讲解会更深入。', like_count: 41, visit_date: '2026-04-25', created_at: '2026-04-26T08:30:00' }
        ],
        avgRating: 4.3,
        ratingDistribution: { '5': 3, '4': 2, '3': 1 },
        total: 6,
        hasMore: false,
        loading: false
      })
    }
  },

  // 评分筛选
  onFilterRating(e) {
    const { rating } = e.currentTarget.dataset
    const newFilter = this.data.ratingFilter === rating ? 0 : rating
    this.setData({ ratingFilter: newFilter, page: 1, hasMore: true, reviews: [] })
    this.loadReviews()
  },

  // 发表评价
  onWriteReview() {
    const token = wx.getStorageSync('token')
    if (!token) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      wx.switchTab({ url: '/pages/mine/mine' })
      return
    }
    this.setData({
      showCommentModal: true,
      commentRating: 5,
      commentContent: '',
      commentVisitDate: ''
    })
  },

  onCloseCommentModal() {
    this.setData({ showCommentModal: false })
  },

  onRatingTap(e) {
    const { rating } = e.currentTarget.dataset
    this.setData({ commentRating: rating })
  },

  onContentInput(e) {
    this.setData({ commentContent: e.detail.value })
  },

  onVisitDateChange(e) {
    this.setData({ commentVisitDate: e.detail.value })
  },

  // 提交评价 → POST /api/scenic/reviews
  async onSubmitReview() {
    const { commentRating, commentContent } = this.data
    if (!commentContent || commentContent.trim().length < 5) {
      wx.showToast({ title: '请输入至少5个字', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    try {
      const spotId = (getApp().globalData.currentScenic || {}).id || 1
      await api.post('/api/scenic/reviews', {
        spot_id: spotId,
        rating: commentRating,
        content: commentContent.trim(),
        visit_date: this.data.commentVisitDate || undefined
      })
      wx.showToast({ title: '评价发表成功', icon: 'success' })
      this.setData({ showCommentModal: false, submitting: false })
      // 刷新列表
      this.setData({ page: 1, hasMore: true })
      this.loadReviews()
    } catch (err) {
      this.setData({ submitting: false })
      wx.showToast({ title: (err && err.msg) || '发表失败', icon: 'none' })
    }
  },

  // 点赞
  onLike(e) {
    const { id } = e.currentTarget.dataset
    const reviews = this.data.reviews.map(r => {
      if (r.id === id) {
        return { ...r, like_count: (r.like_count || 0) + 1, liked: true }
      }
      return r
    })
    this.setData({ reviews })
    wx.showToast({ title: '已点赞', icon: 'none' })
  },

  // 预览图片
  onPreviewImages(e) {
    const { id } = e.currentTarget.dataset
    const review = this.data.reviews.find(r => r.id == id)
    if (!review || !review.images) return
    try {
      const images = typeof review.images === 'string' ? JSON.parse(review.images) : review.images
      if (images && images.length) {
        wx.previewImage({ urls: images, current: images[0] })
      }
    } catch (e) {
      // ignore
    }
  },

  // 获取星星字符串
  _getStars(rating) {
    return '★'.repeat(rating) + '☆'.repeat(5 - rating)
  }
})
