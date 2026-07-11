/**
 * 景区小程序 - 纯JS二维码生成工具
 * 无任何第三方依赖，纯 JavaScript 实现
 * 支持微信小程序 Canvas 2D 渲染
 *
 * 基于 QR Code 标准 (ISO/IEC 18004)
 * 实现: 字节模式编码 + 纠错码M级 + Canvas绘制
 */

// ── QR 常量 ──
const QR_MODE = { NUMERIC: 1, ALPHANUMERIC: 2, BYTE: 4 }
const QR_ECLEVEL = { L: 1, M: 0, Q: 3, H: 2 }

// 对齐模式位置表 (version 2-20)
const ALIGN_PATTERN = [
  [], [6,18], [6,22], [6,26], [6,30], [6,34], [6,22,38], [6,24,42], [6,26,46],
  [6,28,50], [6,30,54], [6,32,58], [6,34,62], [6,26,46,66], [6,26,48,70],
  [6,26,50,74], [6,30,54,78], [6,30,56,82], [6,30,58,86], [6,34,62,90],
  [6,28,50,72,94], [6,26,50,74,98], [6,30,54,78,102], [6,28,54,80,106],
  [6,32,58,84,110], [6,30,58,86,114], [6,34,62,90,118], [6,26,50,74,98,122],
  [6,30,54,78,102,126], [6,26,52,78,104,130], [6,30,56,82,108,134],
  [6,34,60,86,112,138], [6,30,58,86,114,142], [6,34,62,90,118,146],
  [6,30,54,78,102,126,150], [6,24,50,76,102,128,154], [6,28,54,80,106,132,158],
  [6,32,58,84,110,136,162], [6,26,54,82,110,138,166], [6,30,58,86,114,142,170]
]

// 每个版本的容量 (字节模式, EC level M)
// ecLevel 0=M, 1=L, 2=H, 3=Q
const QR_CAPACITY = [
  // version, totalCodewords, ecCodewords per block, blocks group1, dataCodewords group1, blocks group2, dataCodewords group2
  [1, 26, 10, 1, 16],
  [2, 44, 16, 1, 28],
  [3, 70, 26, 1, 44],
  [4, 100, 36, 1, 64],
  [5, 134, 48, 1, 86],
  [6, 172, 64, 1, 108],
  [7, 196, 72, 1, 124],
  [8, 242, 88, 1, 154],
  [9, 292, 110, 1, 182],
  [10, 346, 130, 1, 216],
]

// ── Galois Field 算术 ──
const EXP_TABLE = new Array(256)
const LOG_TABLE = new Array(256)

function initGalois() {
  for (let i = 0; i < 8; i++) {
    EXP_TABLE[i] = 1 << i
  }
  for (let i = 8; i < 256; i++) {
    EXP_TABLE[i] = EXP_TABLE[i-4] ^ EXP_TABLE[i-5] ^ EXP_TABLE[i-6] ^ EXP_TABLE[i-8]
  }
  for (let i = 0; i < 255; i++) {
    LOG_TABLE[EXP_TABLE[i]] = i
  }
}
initGalois()

function gfMul(a, b) {
  if (a === 0 || b === 0) return 0
  return EXP_TABLE[(LOG_TABLE[a] + LOG_TABLE[b]) % 255]
}

function gfPolyMul(p1, p2) {
  const res = new Array(p1.length + p2.length - 1).fill(0)
  for (let i = 0; i < p1.length; i++) {
    for (let j = 0; j < p2.length; j++) {
      res[i+j] ^= gfMul(p1[i], p2[j])
    }
  }
  return res
}

// ── 生成多项式 ──
function getGeneratorPoly(degree) {
  let poly = [1]
  for (let i = 0; i < degree; i++) {
    poly = gfPolyMul(poly, [1, EXP_TABLE[i]])
  }
  return poly
}

// ── Reed-Solomon 编码 ──
function rsEncode(data, ecCount) {
  const gen = getGeneratorPoly(ecCount)
  const msg = new Array(data.length + ecCount).fill(0)
  for (let i = 0; i < data.length; i++) msg[i] = data[i]

  for (let i = 0; i < data.length; i++) {
    const factor = msg[i]
    if (factor !== 0) {
      for (let j = 0; j < gen.length; j++) {
        msg[i+j] ^= gfMul(gen[j], factor)
      }
    }
  }
  const ec = new Array(ecCount)
  for (let i = 0; i < ecCount; i++) {
    ec[i] = msg[data.length + i]
  }
  return [...data, ...ec]
}

// ── QR 矩阵 ──
function createMatrix(version) {
  const size = version * 4 + 17
  const matrix = new Array(size).fill(null).map(() => new Array(size).fill(-1))
  return matrix
}

// 放置查找器图案
function placeFinder(matrix, row, col) {
  for (let r = -1; r <= 7; r++) {
    if (row + r < 0 || row + r >= matrix.length) continue
    for (let c = -1; c <= 7; c++) {
      if (col + c < 0 || col + c >= matrix.length) continue
      if ((r >= 0 && r <= 6 && (c === 0 || c === 6)) ||
          (c >= 0 && c <= 6 && (r === 0 || r === 6)) ||
          (r >= 2 && r <= 4 && c >= 2 && c <= 4)) {
        matrix[row + r][col + c] = 1
      } else if (r >= -1 && r <= 7 && c >= -1 && c <= 7) {
        matrix[row + r][col + c] = 0
      }
    }
  }
}

// 放置对齐图案
function placeAlignment(matrix, centers) {
  for (const row of centers) {
    for (const col of centers) {
      if (matrix[row][col] !== -1) continue
      for (let r = -2; r <= 2; r++) {
        for (let c = -2; c <= 2; c++) {
          if (r === -2 || r === 2 || c === -2 || c === 2 || (r === 0 && c === 0)) {
            matrix[row + r][col + c] = 1
          } else {
            matrix[row + r][col + c] = 0
          }
        }
      }
    }
  }
}

// 放置时序图案
function placeTiming(matrix) {
  const size = matrix.length
  for (let i = 8; i < size - 8; i++) {
    matrix[i][6] = (i % 2 === 0) ? 1 : 0
    matrix[6][i] = (i % 2 === 0) ? 1 : 0
  }
}

// 放置暗模块
function placeDarkModule(matrix) {
  const size = matrix.length
  matrix[size - 8][8] = 1
}

// 预留格式信息区域 (后续填充)
function reserveFormat(matrix) {
  const size = matrix.length
  for (let i = 0; i <= 8; i++) {
    if (matrix[i][8] === -1) matrix[i][8] = 0 // placeholder
    if (matrix[8][i] === -1) matrix[8][i] = 0
  }
  for (let i = size - 1; i >= size - 8; i--) {
    if (matrix[8][i] === -1) matrix[8][i] = 0
    if (matrix[i][8] === -1) matrix[i][8] = 0
  }
}

// 获取掩码计算结果
function getMaskValue(maskPattern, row, col) {
  switch (maskPattern) {
    case 0: return (row + col) % 2 === 0
    case 1: return row % 2 === 0
    case 2: return col % 3 === 0
    case 3: return (row + col) % 3 === 0
    case 4: return (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0
    case 5: return ((row * col) % 2) + ((row * col) % 3) === 0
    case 6: return (((row * col) % 2) + ((row * col) % 3)) % 2 === 0
    case 7: return (((row + col) % 2) + ((row * col) % 3)) % 2 === 0
    default: return false
  }
}

// ── 数据编码 ──
function encodeData(data, version) {
  // 字节模式
  const bytes = []
  for (let i = 0; i < data.length; i++) {
    bytes.push(data.charCodeAt(i) & 0xFF)
  }

  const cap = QR_CAPACITY[version - 1]
  const totalDataBytes = cap[4]  // data codewords per block (for M level)

  // 计算需要的比特数
  const modeIndicator = '0100' // byte mode
  const charCountBits = version <= 9 ? 8 : 16
  const charCount = bytes.length.toString(2).padStart(charCountBits, '0')
  const terminator = '0000'

  let bits = modeIndicator + charCount
  for (const b of bytes) {
    bits += b.toString(2).padStart(8, '0')
  }
  bits += terminator

  // 填充到8的倍数
  while (bits.length % 8 !== 0) bits += '0'

  // 填充到需要的codeword数
  const totalCodewords = cap[1]
  const padBytes = [0xEC, 0x11]
  let padIdx = 0
  while (bits.length / 8 < totalCodewords) {
    bits += padBytes[padIdx].toString(2).padStart(8, '0')
    padIdx = (padIdx + 1) % 2
  }

  // 转换为字节数组
  const codewords = []
  for (let i = 0; i < bits.length; i += 8) {
    codewords.push(parseInt(bits.substring(i, i + 8), 2))
  }

  return codewords
}

// ── 将数据放置到矩阵中 ──
function placeData(matrix, data) {
  const size = matrix.length
  let idx = 0
  let up = true

  for (let col = size - 1; col > 0; col -= 2) {
    if (col === 6) col = 5 // 跳过时序图案列
    for (let k = 0; k < size; k++) {
      const row = up ? size - 1 - k : k
      for (let c = 0; c < 2; c++) {
        const cc = col - c
        if (matrix[row][cc] === -1) {
          if (idx < data.length) {
            matrix[row][cc] = data[idx]
          } else {
            matrix[row][cc] = 0
          }
          idx++
        }
      }
    }
    up = !up
  }
}

// ── 应用掩码 ──
function applyMask(matrix, maskPattern) {
  const size = matrix.length
  // 先保存原矩阵中的功能图案
  const funcPatterns = new Array(size).fill(null).map(() => new Array(size).fill(false))
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      // 查找器图案区域内
      if ((r <= 8 && c <= 8) || (r <= 8 && c >= size - 8) || (r >= size - 8 && c <= 8)) {
        funcPatterns[r][c] = true
      }
    }
  }

  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (funcPatterns[r][c]) continue
      if (getMaskValue(maskPattern, r, c)) {
        matrix[r][c] = matrix[r][c] === 1 ? 0 : (matrix[r][c] === 0 ? 1 : matrix[r][c])
      }
    }
  }
}

// ── 主入口: 生成QR矩阵 ──
function generateQRMatrix(text, version) {
  if (!version) {
    // 自动选择版本
    const len = text.length
    for (let v = 1; v <= QR_CAPACITY.length; v++) {
      if (QR_CAPACITY[v - 1][4] >= len + 3) { // +3 for mode+count overhead
        version = v
        break
      }
    }
    if (!version) version = QR_CAPACITY.length // 用最大版本
  }

  const size = version * 4 + 17
  const matrix = createMatrix(version)

  // 放置功能图案
  placeFinder(matrix, 0, 0)
  placeFinder(matrix, 0, size - 7)
  placeFinder(matrix, size - 7, 0)

  const alignCenters = ALIGN_PATTERN[version - 1]
  if (alignCenters && alignCenters.length > 0) {
    placeAlignment(matrix, alignCenters)
  }

  placeTiming(matrix)
  placeDarkModule(matrix)
  reserveFormat(matrix)

  // 编码数据
  const codewords = encodeData(text, version)
  const cap = QR_CAPACITY[version - 1]

  // Reed-Solomon
  const blockCount = cap[3]
  const dataPerBlock = cap[4]
  const ecPerBlock = cap[2]

  const blocks = []
  for (let i = 0; i < blockCount; i++) {
    const start = i * dataPerBlock
    const blockData = codewords.slice(start, start + dataPerBlock)
    blocks.push(rsEncode(blockData, ecPerBlock))
  }

  // 交错
  const finalData = []
  for (let i = 0; i < dataPerBlock; i++) {
    for (const block of blocks) {
      finalData.push(block[i])
    }
  }
  for (let i = dataPerBlock; i < dataPerBlock + ecPerBlock; i++) {
    for (const block of blocks) {
      finalData.push(block[i])
    }
  }

  // 转换为比特并放置
  const bits = finalData.flatMap(b => {
    const arr = []
    for (let i = 7; i >= 0; i--) {
      arr.push((b >> i) & 1)
    }
    return arr
  })

  placeData(matrix, bits)
  applyMask(matrix, 0) // 使用掩码0

  return { matrix, size, version }
}

// ── Canvas 绘制 (微信小程序 Canvas 2D) ──
// 用法:
//   const query = wx.createSelectorQuery()
//   query.select('#qrCanvas').fields({ node: true, size: true }).exec((res) => {
//     const canvas = res[0].node
//     const ctx = canvas.getContext('2d')
//     drawQRToCanvas(ctx, qrData.matrix, qrData.size, canvas.width, canvas.height)
//   })

function drawQRToCanvas(ctx, matrix, matrixSize, canvasWidth, canvasHeight) {
  const moduleSize = Math.floor(Math.min(canvasWidth, canvasHeight) / (matrixSize + 8)) // +8 padding
  const offsetX = Math.floor((canvasWidth - moduleSize * matrixSize) / 2)
  const offsetY = Math.floor((canvasHeight - moduleSize * matrixSize) / 2)

  // 清除画布
  ctx.clearRect(0, 0, canvasWidth, canvasHeight)

  // 背景白色
  ctx.fillStyle = '#FFFFFF'
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  // 绘制 QR 模块
  ctx.fillStyle = '#000000'
  for (let r = 0; r < matrixSize; r++) {
    for (let c = 0; c < matrixSize; c++) {
      if (matrix[r][c] === 1) {
        ctx.fillRect(
          offsetX + c * moduleSize,
          offsetY + r * moduleSize,
          moduleSize,
          moduleSize
        )
      }
    }
  }
}

// ── 简单绘制 (使用旧版 Canvas API, 兼容性更好) ──
// 用法:
//   const ctx = wx.createCanvasContext('qrCanvas')
//   drawQRToCanvasContext(ctx, qrData.matrix, qrData.size, 300, 300)
//   ctx.draw()

function drawQRToCanvasContext(ctx, matrix, matrixSize, canvasWidth, canvasHeight) {
  const moduleSize = Math.floor(Math.min(canvasWidth, canvasHeight) / (matrixSize + 8))
  const offsetX = Math.floor((canvasWidth - moduleSize * matrixSize) / 2)
  const offsetY = Math.floor((canvasHeight - moduleSize * matrixSize) / 2)

  // 背景
  ctx.setFillStyle('#FFFFFF')
  ctx.fillRect(0, 0, canvasWidth, canvasHeight)

  // 黑色模块
  ctx.setFillStyle('#000000')
  for (let r = 0; r < matrixSize; r++) {
    for (let c = 0; c < matrixSize; c++) {
      if (matrix[r][c] === 1) {
        ctx.fillRect(
          offsetX + c * moduleSize,
          offsetY + r * moduleSize,
          moduleSize,
          moduleSize
        )
      }
    }
  }
}

module.exports = {
  generateQRMatrix,
  drawQRToCanvas,
  drawQRToCanvasContext,
  QR_MODE,
  QR_ECLEVEL
}
