# 三系统巡检清单 v1.0
## 每次代码变更后必须执行

### 1. API 前缀检查
grep -r "fetch.*'/api/" admin/pages/ | grep -v '/scenic/api/'
# 景区必须零结果。酒店可以。
# 景区所有API调用必须是 /scenic/api/ 不是 /api/

### 2. 硬编码检查
grep -r "admin123\|password" admin/pages/ --include="*.html"
# 三系统必须零结果

### 3. 部署验证（服务器端）
curl -s http://127.0.0.1:8001/api/hotels | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('code')==0 else d.get('detail','FAIL'))"
curl -s http://127.0.0.1:8002/api/hotels | python3 -c "import sys,json;print(len(json.load(sys.stdin)))"
curl -s http://127.0.0.1:8000/health

### 4. 登录流程验证
# 酒店: admin/admin123 → 进管理面板
# 景区: admin/admin123 → 进管理面板
# 公寓: 13800000000/admin123 → 进后台

### 5. 各页面快速抽查
# 至少抽查3个页面能正常加载（非404非空壳）
