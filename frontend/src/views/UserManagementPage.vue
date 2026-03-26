<template>
  <div class="user-management-container">
    <h1>用户管理</h1>
    
    <!-- 标签页 -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="用户管理" name="users">
        <div class="tab-content">
          <!-- 新增用户按钮 -->
          <el-button type="primary" @click="openAddUserDialog">新增用户</el-button>
          
          <!-- 用户列表 -->
          <el-table :data="users" style="width: 100%" border>
            <el-table-column prop="username" label="用户名" width="180"></el-table-column>
            <el-table-column prop="is_admin" label="是否管理员" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.is_admin ? 'success' : 'info'">
                  {{ scope.row.is_admin ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间"></el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="scope">
                <el-button type="primary" size="small" @click="openEditUserDialog(scope.row)">编辑</el-button>
                <el-button type="danger" size="small" @click="deleteUser(scope.row)" v-if="!scope.row.is_admin">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
      
      <el-tab-pane label="任务管理" name="tasks">
        <div class="tab-content">
          <!-- 新增任务按钮 -->
          <el-button type="primary" @click="openAddTaskDialog">新增任务</el-button>
          
          <!-- 任务列表 -->
          <el-table :data="tasks" style="width: 100%" border>
            <el-table-column prop="task_name" label="任务名称" width="180"></el-table-column>
            <el-table-column prop="description" label="描述"></el-table-column>
            <el-table-column prop="is_default" label="是否默认" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.is_default ? 'success' : 'info'">
                  {{ scope.row.is_default ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间"></el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="scope">
                <el-button type="primary" size="small" @click="openEditTaskDialog(scope.row)">编辑</el-button>
                <el-button type="danger" size="small" @click="deleteTask(scope.row)" v-if="!scope.row.is_default">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
    
    <!-- 新增用户对话框 -->
    <el-dialog
      v-model="addUserDialogVisible"
      title="新增用户"
      width="400px"
    >
      <el-form
        ref="addUserFormRef"
        :model="addUserForm"
        :rules="userFormRules"
        label-width="80px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="addUserForm.username" placeholder="请输入用户名"></el-input>
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input v-model="addUserForm.password" type="password" placeholder="请输入密码"></el-input>
        </el-form-item>
        
        <el-form-item label="是否管理员">
          <el-switch v-model="addUserForm.is_admin"></el-switch>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addUserDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="addUser" :loading="isLoading">确定</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 编辑用户对话框 -->
    <el-dialog
      v-model="editUserDialogVisible"
      title="编辑用户"
      width="400px"
    >
      <el-form
        ref="editUserFormRef"
        :model="editUserForm"
        :rules="userFormRules"
        label-width="80px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="editUserForm.username" placeholder="请输入用户名"></el-input>
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input v-model="editUserForm.password" type="password" placeholder="请输入密码（不修改请留空）"></el-input>
        </el-form-item>
        
        <el-form-item label="是否管理员">
          <el-switch v-model="editUserForm.is_admin" :disabled="editUserForm.is_admin"></el-switch>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editUserDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="updateUser" :loading="isLoading">确定</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 新增任务对话框 -->
    <el-dialog
      v-model="addTaskDialogVisible"
      title="新增任务"
      width="400px"
    >
      <el-form
        ref="addTaskFormRef"
        :model="addTaskForm"
        :rules="taskFormRules"
        label-width="80px"
      >
        <el-form-item label="任务名称" prop="task_name">
          <el-input v-model="addTaskForm.task_name" placeholder="请输入任务名称"></el-input>
        </el-form-item>
        
        <el-form-item label="描述" prop="description">
          <el-input v-model="addTaskForm.description" type="textarea" placeholder="请输入任务描述"></el-input>
        </el-form-item>
        
        <el-form-item label="是否默认">
          <el-switch v-model="addTaskForm.is_default"></el-switch>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addTaskDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="addTask" :loading="isLoading">确定</el-button>
        </span>
      </template>
    </el-dialog>
    
    <!-- 编辑任务对话框 -->
    <el-dialog
      v-model="editTaskDialogVisible"
      title="编辑任务"
      width="400px"
    >
      <el-form
        ref="editTaskFormRef"
        :model="editTaskForm"
        :rules="taskFormRules"
        label-width="80px"
      >
        <el-form-item label="任务名称" prop="task_name">
          <el-input v-model="editTaskForm.task_name" placeholder="请输入任务名称"></el-input>
        </el-form-item>
        
        <el-form-item label="描述" prop="description">
          <el-input v-model="editTaskForm.description" type="textarea" placeholder="请输入任务描述"></el-input>
        </el-form-item>
        
        <el-form-item label="是否默认">
          <el-switch v-model="editTaskForm.is_default" :disabled="editTaskForm.is_default"></el-switch>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="editTaskDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="updateTask" :loading="isLoading">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index.js'

// 状态
const activeTab = ref('users')
const users = ref([])
const tasks = ref([])
const isLoading = ref(false)

// 对话框状态
const addUserDialogVisible = ref(false)
const editUserDialogVisible = ref(false)
const addTaskDialogVisible = ref(false)
const editTaskDialogVisible = ref(false)

// 表单数据
const addUserForm = reactive({
  username: '',
  password: '',
  is_admin: false
})

const editUserForm = reactive({
  user_id: '',
  username: '',
  password: '',
  is_admin: false
})

const addTaskForm = reactive({
  task_name: '',
  description: '',
  is_default: false
})

const editTaskForm = reactive({
  task_id: '',
  task_name: '',
  description: '',
  is_default: false
})

// 表单规则
const userFormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

const taskFormRules = {
  task_name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' }
  ]
}

// 表单引用
const addUserFormRef = ref(null)
const editUserFormRef = ref(null)
const addTaskFormRef = ref(null)
const editTaskFormRef = ref(null)

// 加载用户列表
const loadUsers = async () => {
  try {
    const res = await api.get('/auth/users')
    users.value = res.data.users
  } catch (error) {
    ElMessage.error('加载用户列表失败: ' + error.message)
  }
}

// 加载任务列表
const loadTasks = async () => {
  try {
    const res = await api.get('/auth/tasks')
    tasks.value = res.data.tasks
  } catch (error) {
    ElMessage.error('加载任务列表失败: ' + error.message)
  }
}

// 打开新增用户对话框
const openAddUserDialog = () => {
  // 重置表单
  addUserForm.username = ''
  addUserForm.password = ''
  addUserForm.is_admin = false
  addUserDialogVisible.value = true
}

// 打开编辑用户对话框
const openEditUserDialog = (user) => {
  editUserForm.user_id = user.user_id
  editUserForm.username = user.username
  editUserForm.is_admin = user.is_admin
  editUserForm.password = '' // 密码留空
  editUserDialogVisible.value = true
}

// 打开新增任务对话框
const openAddTaskDialog = () => {
  // 重置表单
  addTaskForm.task_name = ''
  addTaskForm.description = ''
  addTaskForm.is_default = false
  addTaskDialogVisible.value = true
}

// 打开编辑任务对话框
const openEditTaskDialog = (task) => {
  editTaskForm.task_id = task.task_id
  editTaskForm.task_name = task.task_name
  editTaskForm.description = task.description
  editTaskForm.is_default = task.is_default
  editTaskDialogVisible.value = true
}

// 新增用户
const addUser = async () => {
  if (!addUserFormRef.value) return
  
  try {
    await addUserFormRef.value.validate()
    isLoading.value = true
    
    const res = await api.post('/auth/users', addUserForm)
    if (res.data.success) {
      ElMessage.success('用户创建成功')
      addUserDialogVisible.value = false
      await loadUsers()
    }
  } catch (error) {
    ElMessage.error('创建用户失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isLoading.value = false
  }
}

// 更新用户
const updateUser = async () => {
  if (!editUserFormRef.value) return
  
  try {
    await editUserFormRef.value.validate()
    isLoading.value = true
    
    const res = await api.put(`/auth/users/${editUserForm.user_id}`, {
      username: editUserForm.username,
      password: editUserForm.password || undefined,
      is_admin: editUserForm.is_admin
    })
    
    if (res.data.success) {
      ElMessage.success('用户更新成功')
      editUserDialogVisible.value = false
      await loadUsers()
    }
  } catch (error) {
    ElMessage.error('更新用户失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isLoading.value = false
  }
}

// 删除用户
const deleteUser = async (user) => {
  try {
    await ElMessageBox.confirm('确定要删除用户 ' + user.username + ' 吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    isLoading.value = true
    const res = await api.delete(`/auth/users/${user.user_id}`)
    
    if (res.data.success) {
      ElMessage.success('用户删除成功')
      await loadUsers()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除用户失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    isLoading.value = false
  }
}

// 新增任务
const addTask = async () => {
  if (!addTaskFormRef.value) return
  
  try {
    await addTaskFormRef.value.validate()
    isLoading.value = true
    
    const res = await api.post('/auth/tasks', addTaskForm)
    if (res.data.success) {
      ElMessage.success('任务创建成功')
      addTaskDialogVisible.value = false
      await loadTasks()
    }
  } catch (error) {
    ElMessage.error('创建任务失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isLoading.value = false
  }
}

// 更新任务
const updateTask = async () => {
  if (!editTaskFormRef.value) return
  
  try {
    await editTaskFormRef.value.validate()
    isLoading.value = true
    
    const res = await api.put(`/auth/tasks/${editTaskForm.task_id}`, {
      task_name: editTaskForm.task_name,
      description: editTaskForm.description,
      is_default: editTaskForm.is_default
    })
    
    if (res.data.success) {
      ElMessage.success('任务更新成功')
      editTaskDialogVisible.value = false
      await loadTasks()
    }
  } catch (error) {
    ElMessage.error('更新任务失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    isLoading.value = false
  }
}

// 删除任务
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要删除任务 ' + task.task_name + ' 吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    isLoading.value = true
    const res = await api.delete(`/auth/tasks/${task.task_id}`)
    
    if (res.data.success) {
      ElMessage.success('任务删除成功')
      await loadTasks()
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除任务失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    isLoading.value = false
  }
}

// 初始化
onMounted(async () => {
  await loadUsers()
  await loadTasks()
})
</script>

<style scoped>
.user-management-container {
  padding: 20px;
}

.tab-content {
  margin-top: 20px;
}

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
}
</style>
