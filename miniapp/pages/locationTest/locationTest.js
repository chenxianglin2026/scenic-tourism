Page({
  getNowLocation() {
    wx.getLocation({ type: 'gcj02', success: (res) => { console.log('经纬度', res.latitude, res.longitude); wx.showToast({title:'定位获取成功'}) }, fail: (err) => { console.log('定位失败',err) } })
  },
  openMapSelect() {
    wx.chooseLocation({ success:(res)=>{ console.log('选择点位',res.name,res.address) } })
  },
  selectScenicPoi(){
    wx.choosePoi({ success:(res)=>{ console.log('选中POI',res.poiList) } })
  }
})
