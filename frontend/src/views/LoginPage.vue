<template>
  <div class="login-container">
    <div class="login-form">
      <h1 class="login-title">语音采集系统登录</h1>
      
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-width="80px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="loginForm.username" placeholder="请输入用户名"></el-input>
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码"></el-input>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleLogin" :loading="isLoading">登录</el-button>
          <el-button @click="handleRegister">注册</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 注册表单 -->
      <el-dialog
        v-model="registerDialogVisible"
        title="用户注册"
        width="400px"
      >
        <el-form
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          label-width="80px"
        >
          <el-form-item label="用户名" prop="username">
            <el-input v-model="registerForm.username" placeholder="请输入用户名"></el-input>
          </el-form-item>
          
          <el-form-item label="密码" prop="password">
            <el-input v-model="registerForm.password" type="password" placeholder="请输入密码"></el-input>
          </el-form-item>
          
          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请确认密码"></el-input>
          </el-form-item>
        </el-form>
        
        <template #footer>
          <span class="dialog-footer">
            <el-button @click="registerDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleRegisterSubmit" :loading="isRegistering">注册</el-button>
          </span>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index.js'

const router = useRouter()

// 登录表单
const loginForm = reactive({
  username: '',
  password: ''
})

// 登录表单规则
const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

// 注册表单
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

// 注册表单规则
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 状态
const isLoading = ref(false)
const isRegistering = ref(false)
const registerDialogVisible = ref(false)

// 登录表单引用
const loginFormRef = ref(null)
const registerFormRef = ref(null)

// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  try {
    await loginFormRef.value.validate()
    isLoading.value = true
    
    const res = await api.post('/auth/login', 
      `username=${encodeURIComponent(loginForm.username)}&password=${encodeURIComponent(loginForm.password)}`,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    )
    
    if (res.data.access_token) {
      // 保存token到本地存储
      localStorage.setItem('token', res.data.access_token)
      localStorage.setItem('user', JSON.stringify(res.data.user))
      
      ElMessage.success('登录成功')
      router.push('/')
    }
  } catch (error) {
    ElMessage.error('登录失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isLoading.value = false
  }
}

// 打开注册对话框
const handleRegister = () => {
  registerDialogVisible.value = true
}

// 处理注册提交
const handleRegisterSubmit = async () => {
  if (!registerFormRef.value) return
  
  try {
    await registerFormRef.value.validate()
    isRegistering.value = true
    
    const res = await api.post('/auth/register', 
      `username=${encodeURIComponent(registerForm.username)}&password=${encodeURIComponent(registerForm.password)}`,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    )
    
    if (res.data.success) {
      ElMessage.success('注册成功，请登录')
      registerDialogVisible.value = false
    }
  } catch (error) {
    ElMessage.error('注册失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isRegistering.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}

.login-form {
  width: 400px;
  padding: 30px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.login-title {
  text-align: center;
  margin-bottom: 20px;
  color: #303133;
}

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}
</style>
