# 解决 Vite 依赖锁定错误

## 错误信息
```
Error: EBUSY: resource busy or locked, rename '...\node_modules\.vite\deps_temp_xxx' -> '...\node_modules\.vite\deps'
```

这是 Windows 系统上常见的文件锁定问题。

---

## 解决方案（按顺序尝试）

### 方案1：快速修复（推荐）

1. **关闭所有 Node 进程**
   - 按 `Ctrl + Shift + Esc` 打开任务管理器
   - 结束所有 `node.exe` 进程

2. **运行修复脚本**
   ```bash
   cd frontend
   fix-vite-error.bat
   ```

3. **重新启动**
   ```bash
   npm run dev
   ```

---

### 方案2：手动清理

1. **关闭所有相关进程**
   - 关闭所有命令行窗口
   - 关闭 VS Code 或其他编辑器
   - 结束任务管理器中的 Node 进程

2. **删除 Vite 缓存**
   ```bash
   cd frontend
   rmdir /s /q node_modules\.vite
   ```

3. **重新启动**
   ```bash
   npm run dev
   ```

---

### 方案3：完全重新安装（如果方案1、2都不行）

1. **运行清理脚本**
   ```bash
   cd frontend
   clean-install.bat
   ```

   或手动执行：
   ```bash
   # 关闭所有 Node 进程
   taskkill /F /IM node.exe
   
   # 删除依赖
   rmdir /s /q node_modules
   del package-lock.json
   
   # 重新安装
   npm install
   ```

2. **重新启动**
   ```bash
   npm run dev
   ```

---

### 方案4：使用国内镜像（如果安装慢）

```bash
npm install --registry=https://registry.npmmirror.com
```

或设置永久镜像：
```bash
npm config set registry https://registry.npmmirror.com
```

---

## 预防措施

### 1. 正确关闭开发服务器
- 使用 `Ctrl + C` 停止服务器
- 等待进程完全退出后再关闭终端

### 2. 避免同时运行多个实例
- 确保只有一个 `npm run dev` 在运行
- 检查端口占用：`netstat -ano | findstr :3000`

### 3. 配置 Vite（已更新）
已在 `vite.config.js` 中添加：
```js
optimizeDeps: {
  force: true
}
```

---

## 如果问题仍然存在

### 检查防病毒软件
- 某些防病毒软件会锁定 `node_modules` 目录
- 将项目目录添加到防病毒软件的白名单

### 检查文件权限
- 确保对项目目录有完全控制权限
- 右键项目文件夹 → 属性 → 安全 → 编辑权限

### 使用管理员权限
- 右键命令行 → 以管理员身份运行
- 然后执行 `npm run dev`

---

## 常见问题

### Q: 为什么会出现这个错误？
A: Windows 文件系统在文件被占用时不允许重命名，Vite 在更新依赖时需要重命名临时目录。

### Q: 会影响项目功能吗？
A: 不会，这只是开发环境的缓存问题，不影响实际功能。

### Q: 每次都要这样修复吗？
A: 通常只需要修复一次，后续正常关闭服务器就不会再出现。

---

## 快速命令参考

```bash
# 快速修复
cd frontend && fix-vite-error.bat && npm run dev

# 完全重装
cd frontend && clean-install.bat && npm run dev

# 手动清理
taskkill /F /IM node.exe
rmdir /s /q node_modules\.vite
npm run dev
```



