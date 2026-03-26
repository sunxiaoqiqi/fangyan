<template>
  <div id="app">
    <el-container>
      <el-header>
        <div class="header-content">
          <h1>辰溪话语音采集系统</h1>
          <div class="header-right">
            <div class="nav-links">
              <router-link to="/">采集</router-link>
              <router-link to="/transcribe">标注</router-link>
              <router-link to="/fine-tune">微调</router-link>
              <router-link to="/fine-tune-history">微调记录</router-link>
              <router-link to="/evaluate">评估</router-link>
              <router-link to="/test">测试</router-link>
              <router-link to="/user-management" v-if="user && user.is_admin">用户管理</router-link>
            </div>
            <div class="user-info" v-if="user">
              <span class="username">{{ user.username }}</span>
              <el-button type="text" @click="handleLogout" style="color: white;">登出</el-button>
            </div>
          </div>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const user = ref(null)

// 加载用户信息
const loadUserInfo = () => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    user.value = JSON.parse(userStr)
  }
}

// 处理登出
const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  user.value = null
  ElMessage.success('登出成功')
  router.push('/login')
}

onMounted(() => {
  // 初始化说话人ID（如果不存在）
  if (!localStorage.getItem('speaker_id')) {
    const speakerId = 'spk_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
    localStorage.setItem('speaker_id', speakerId)
  }
  
  // 加载用户信息
  loadUserInfo()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  min-height: 100vh;
  background: #f5f5f5;
}

.el-header {
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.username {
  font-size: 14px;
  margin-right: 10px;
}

.header-content h1 {
  font-size: 24px;
  font-weight: 500;
  margin: 0;
}

.nav-links {
  display: flex;
  gap: 20px;
}

.nav-links a {
  color: white;
  text-decoration: none;
  padding: 5px 15px;
  border-radius: 4px;
  transition: background 0.3s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  background: rgba(255, 255, 255, 0.2);
}

.el-main {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

/* 手机端响应式设计 */
@media screen and (max-width: 768px) {
  .el-header {
    padding: 0 10px;
  }
  
  .header-content {
    flex-direction: column;
    padding: 10px 0;
  }
  
  .header-content h1 {
    font-size: 18px;
    margin-bottom: 10px;
  }
  
  .header-right {
    flex-direction: column;
    gap: 10px;
    width: 100%;
  }
  
  .nav-links {
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
  }
  
  .nav-links a {
    padding: 5px 10px;
    font-size: 12px;
  }
  
  .user-info {
    justify-content: center;
  }
  
  .el-main {
    padding: 10px;
  }
}

/* 小屏幕手机 */
@media screen and (max-width: 480px) {
  .header-content h1 {
    font-size: 16px;
  }
  
  .nav-links {
    gap: 5px;
  }
  
  .nav-links a {
    padding: 3px 8px;
    font-size: 11px;
  }
}
</style>

