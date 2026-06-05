/**
 * 景区智慧管理系统小程序 - 常量配置
 */

const config = {
  // ═══════════════════════════════════════════
  // API 配置
  // ═══════════════════════════════════════════

  /** API 基础地址 */
  API_BASE: 'http://43.163.5.90:8001',

  /** 开发模式 */
  DEV_MODE: false,

  // ═══════════════════════════════════════════
  // 业务常量
  // ═══════════════════════════════════════════

  /** 门票类型 */
  TICKET_TYPES: {
    adult:    { label: '成人票',  icon: '🧑', desc: '18-60周岁成人' },
    child:    { label: '儿童票',  icon: '👶', desc: '6-18周岁儿童' },
    senior:   { label: '老年票',  icon: '👴', desc: '60周岁以上老人' },
    student:  { label: '学生票',  icon: '🎓', desc: '全日制学生' },
    family:   { label: '家庭套票', icon: '👨‍👩‍👧', desc: '2大1小家庭套票' },
    annual:   { label: '年卡',    icon: '💳', desc: '全年不限次入园' },
  },

  /** 门票时段 */
  TIME_SLOTS: {
    morning:   { label: '上午场', time: '08:00-12:00', desc: '上午入园' },
    afternoon: { label: '下午场', time: '12:00-17:30', desc: '下午入园' },
    allday:    { label: '全天',   time: '08:00-17:30', desc: '全天畅玩' },
  },

  /** 订单状态 */
  ORDER_STATUS: {
    unpaid:     { label: '待支付',   color: '#E8A838', bg: '#FFF8E8' },
    paid:       { label: '已支付',   color: '#5B8DEF', bg: '#EDF4FF' },
    verified:   { label: '已核销',   color: '#6BAA75', bg: '#F0FAF0' },
    refunded:   { label: '已退款',   color: '#C56C6C', bg: '#FFF0F0' },
    expired:    { label: '已过期',   color: '#B0A492', bg: '#F5F5F5' },
    cancelled:  { label: '已取消',   color: '#B0A492', bg: '#F5F5F5' },
  },

  /** 客房状态 */
  ROOM_STATUS: {
    available:   { label: '可预订', color: '#6BAA75' },
    booked:      { label: '已预订', color: '#5B8DEF' },
    occupied:    { label: '入住中', color: '#C56C6C' },
    cleaning:    { label: '清洁中', color: '#E8A838' },
    maintenance: { label: '维护中', color: '#B0A492' },
  },

  // ═══════════════════════════════════════════
  // 存储 Key
  // ═══════════════════════════════════════════

  STORAGE_KEYS: {
    TOKEN: 'token',
    USER_INFO: 'userInfo',
    LOCATION: 'location',
    REAL_NAME: 'realName',
    ID_CARD: 'idCard',
  },

  // ═══════════════════════════════════════════
  // 分页默认值
  // ═══════════════════════════════════════════

  PAGE_SIZE: 20,
  PAGE_SIZE_SMALL: 10,
}

module.exports = config
