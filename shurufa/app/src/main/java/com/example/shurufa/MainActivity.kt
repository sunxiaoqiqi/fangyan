package com.example.shurufa

import android.content.pm.PackageManager
import android.media.MediaPlayer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.core.app.ActivityCompat
import com.example.shurufa.ui.theme.ShurufaTheme
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*

class MainActivity : ComponentActivity() {
    private var mediaPlayer: MediaPlayer? = null
    private var isPlaying = mutableStateOf(false)
    private var currentPosition = mutableStateOf(0)
    private var duration = mutableStateOf(0)
    
    // 录音列表数据
    private val recordingsList = mutableStateListOf<RecordingItem>()
    private var currentlyPlayingFile: String? = null
    private var searchQuery = mutableStateOf("")
    
    data class RecordingItem(
        val file: File,
        val fileName: String,
        val timestamp: Long,
        val fileSize: Long,
        val duration: Int = 0
    ) {
        val formattedDate: String
            get() {
                val sdf = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault())
                return sdf.format(Date(timestamp))
            }
        
        val formattedSize: String
            get() {
                return when {
                    fileSize < 1024 -> "$fileSize B"
                    fileSize < 1024 * 1024 -> "${fileSize / 1024} KB"
                    else -> String.format("%.2f MB", fileSize / (1024.0 * 1024.0))
                }
            }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        
        // 申请录音权限
        requestAudioPermission()
        
        setContent {
            ShurufaTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) {
                    innerPadding ->
                    DebugScreen(
                        modifier = Modifier.padding(innerPadding),
                        onRecordingClick = ::playRecording,
                        isPlaying = isPlaying.value,
                        currentPosition = currentPosition.value,
                        duration = duration.value,
                        recordingsList = recordingsList,
                        currentlyPlayingFile = currentlyPlayingFile,
                        searchQuery = searchQuery,
                        onPlayClick = { file -> playRecordingFile(file) },
                        onStopClick = { stopPlayback() },
                        onDeleteClick = { file -> deleteRecording(file) },
                        onSearchQueryChange = { searchQuery.value = it },
                        onRefresh = { loadRecordingsList() }
                    )
                }
            }
        }
        
        // 加载录音列表
        loadRecordingsList()
        
        // 启动播放进度更新
        startProgressUpdate()
    }
    
    private fun loadRecordingsList() {
        // 优先从外部Downloads目录读取
        val downloadsDir = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS)
        val cacheDir = cacheDir
        
        val allFiles = mutableListOf<File>()
        
        // 添加Downloads目录的文件
        downloadsDir?.let { dir ->
            if (dir.exists()) {
                dir.listFiles { file -> 
                    file.isFile && file.name.startsWith("voice_input_") && file.name.endsWith(".wav")
                }?.let { files -> allFiles.addAll(files) }
            }
        }
        
        // 添加cache目录的文件
        cacheDir.listFiles { file -> 
            file.isFile && file.name.startsWith("voice_input_") && file.name.endsWith(".wav")
        }?.let { files -> allFiles.addAll(files) }
        
        // 转换为RecordingItem并按时间倒序排列
        val items = allFiles.map { file ->
            RecordingItem(
                file = file,
                fileName = file.name,
                timestamp = file.lastModified(),
                fileSize = file.length()
            )
        }.sortedByDescending { it.timestamp }
        
        recordingsList.clear()
        recordingsList.addAll(items)
        
        println("加载了 ${recordingsList.size} 个录音文件")
    }
    
    private fun playRecordingFile(file: File) {
        try {
            mediaPlayer?.stop()
            mediaPlayer?.release()
            mediaPlayer = null
            
            mediaPlayer = MediaPlayer()
            mediaPlayer?.setDataSource(file.absolutePath)
            mediaPlayer?.prepare()
            mediaPlayer?.start()
            
            currentlyPlayingFile = file.absolutePath
            isPlaying.value = true
            duration.value = mediaPlayer?.duration ?: 0
            
            mediaPlayer?.setOnCompletionListener {
                isPlaying.value = false
                currentPosition.value = 0
                currentlyPlayingFile = null
            }
        } catch (e: IOException) {
            e.printStackTrace()
            Toast.makeText(this, "播放失败: ${e.message}", Toast.LENGTH_SHORT).show()
            isPlaying.value = false
            currentlyPlayingFile = null
        }
    }
    
    private fun stopPlayback() {
        mediaPlayer?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
        isPlaying.value = false
        currentPosition.value = 0
        currentlyPlayingFile = null
    }
    
    private fun deleteRecording(file: File) {
        if (currentlyPlayingFile == file.absolutePath) {
            stopPlayback()
        }
        
        if (file.delete()) {
            recordingsList.removeIf { it.file.absolutePath == file.absolutePath }
            Toast.makeText(this, "录音已删除", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "删除失败", Toast.LENGTH_SHORT).show()
        }
    }
    
    private fun requestAudioPermission() {
        if (ActivityCompat.checkSelfPermission(
                this,
                android.Manifest.permission.RECORD_AUDIO
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(android.Manifest.permission.RECORD_AUDIO),
                1001
            )
        }
    }
    
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 1001) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Toast.makeText(this, "录音权限已授予", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "请在设置中开启录音权限", Toast.LENGTH_SHORT).show()
            }
        }
    }
    
    private fun startProgressUpdate() {
        val handler = Handler(Looper.getMainLooper())
        val runnable = object : Runnable {
            override fun run() {
                if (isPlaying.value) {
                    currentPosition.value = mediaPlayer?.currentPosition ?: 0
                    duration.value = mediaPlayer?.duration ?: 0
                    handler.postDelayed(this, 100)
                }
            }
        }
        handler.post(runnable)
    }
    
    private fun playRecording() {
        // 这个方法保留用于向后兼容，但不再使用
        Toast.makeText(this, "请从下方列表选择录音播放", Toast.LENGTH_SHORT).show()
    }
    
    override fun onDestroy() {
        super.onDestroy()
        mediaPlayer?.stop()
        mediaPlayer?.release()
    }
}

@Composable
fun DebugScreen(
    modifier: Modifier = Modifier,
    onRecordingClick: () -> Unit,
    isPlaying: Boolean,
    currentPosition: Int,
    duration: Int,
    recordingsList: List<MainActivity.RecordingItem>,
    currentlyPlayingFile: String?,
    searchQuery: State<String>,
    onPlayClick: (File) -> Unit,
    onStopClick: () -> Unit,
    onDeleteClick: (File) -> Unit,
    onSearchQueryChange: (String) -> Unit,
    onRefresh: () -> Unit
) {
    val context = LocalContext.current
    var inputText by remember { mutableStateOf("") }
    var progress by remember { mutableStateOf(0f) }
    
    // 计算播放进度
    progress = if (duration > 0) {
        currentPosition.toFloat() / duration.toFloat()
    } else {
        0f
    }
    
    // 过滤录音列表
    val filteredList = if (searchQuery.value.isEmpty()) {
        recordingsList
    } else {
        recordingsList.filter { 
            it.fileName.contains(searchQuery.value, ignoreCase = true) ||
            it.formattedDate.contains(searchQuery.value, ignoreCase = true)
        }
    }
    
    // 权限请求
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (!isGranted) {
            Toast.makeText(context, "需要录音权限", Toast.LENGTH_SHORT).show()
        }
    }
    
    // 检查并请求权限
    if (ActivityCompat.checkSelfPermission(
            context,
            android.Manifest.permission.RECORD_AUDIO
        ) != PackageManager.PERMISSION_GRANTED
    ) {
        permissionLauncher.launch(android.Manifest.permission.RECORD_AUDIO)
    }
    
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // 标题
        Text(
            text = "输入法调试页面",
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(bottom = 8.dp)
        )
        
        // 输入框
        OutlinedTextField(
            value = inputText,
            onValueChange = { inputText = it },
            label = { Text("点击此处唤醒输入法") },
            modifier = Modifier
                .fillMaxWidth()
                .height(100.dp),
            maxLines = 3
        )
        
        // 全局播放进度显示
        if (currentlyPlayingFile != null && duration > 0) {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp)
            ) {
                Column(
                    modifier = Modifier.padding(12.dp)
                ) {
                    Text(
                        text = "正在播放: ${File(currentlyPlayingFile).name}",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    LinearProgressIndicator(
                        progress = { progress },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text(
                        text = "${formatTime(currentPosition)} / ${formatTime(duration)}",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(
                        onClick = onStopClick,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Pause, contentDescription = "停止")
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("停止播放")
                    }
                }
            }
        }
        
        // 录音列表标题和搜索框
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "录音列表 (${filteredList.size})",
                style = MaterialTheme.typography.titleMedium
            )
            IconButton(onClick = onRefresh) {
                Icon(Icons.Default.Refresh, contentDescription = "刷新")
            }
        }
        
        // 搜索框
        OutlinedTextField(
            value = searchQuery.value,
            onValueChange = onSearchQueryChange,
            label = { Text("搜索录音") },
            leadingIcon = { Icon(Icons.Default.Refresh, contentDescription = null) },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        
        Spacer(modifier = Modifier.height(8.dp))
        
        // 录音列表
        if (filteredList.isEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "暂无录音",
                        style = MaterialTheme.typography.bodyLarge
                    )
                    Text(
                        text = "使用输入法录音后，录音将显示在这里",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(filteredList, key = { it.file.absolutePath }) { recording ->
                    RecordingListItem(
                        recording = recording,
                        isPlaying = currentlyPlayingFile == recording.file.absolutePath,
                        onPlayClick = { onPlayClick(recording.file) },
                        onStopClick = onStopClick,
                        onDeleteClick = { onDeleteClick(recording.file) }
                    )
                }
            }
        }
        
        // 提示信息
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 8.dp)
        ) {
            Text(
                text = "提示：\n" +
                        "1. 点击输入框唤醒输入法\n" +
                        "2. 使用输入法的语音输入功能\n" +
                        "3. 录音完成后，录音将显示在列表中\n" +
                        "4. 点击播放按钮可以播放录音",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(12.dp)
            )
        }
    }
}

@Composable
fun RecordingListItem(
    recording: MainActivity.RecordingItem,
    isPlaying: Boolean,
    onPlayClick: () -> Unit,
    onStopClick: () -> Unit,
    onDeleteClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 录音信息
            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = recording.fileName,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = "${recording.formattedDate} • ${recording.formattedSize}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            
            // 播放/停止按钮
            IconButton(
                onClick = if (isPlaying) onStopClick else onPlayClick
            ) {
                Icon(
                    imageVector = if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                    contentDescription = if (isPlaying) "暂停" else "播放",
                    tint = if (isPlaying) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                )
            }
            
            // 删除按钮
            IconButton(onClick = onDeleteClick) {
                Icon(
                    imageVector = Icons.Default.Delete,
                    contentDescription = "删除",
                    tint = MaterialTheme.colorScheme.error
                )
            }
        }
        
        // 播放时显示进度条
        if (isPlaying) {
            LinearProgressIndicator(
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

private fun formatTime(milliseconds: Int): String {
    val seconds = (milliseconds / 1000) % 60
    val minutes = (milliseconds / (1000 * 60)) % 60
    val hours = (milliseconds / (1000 * 60 * 60))
    
    return if (hours > 0) {
        String.format("%02d:%02d:%02d", hours, minutes, seconds)
    } else {
        String.format("%02d:%02d", minutes, seconds)
    }
}

@Preview(showBackground = true)
@Composable
fun DebugScreenPreview() {
    ShurufaTheme {
        DebugScreen(
            onRecordingClick = {},
            isPlaying = false,
            currentPosition = 30000,
            duration = 60000,
            recordingsList = emptyList(),
            currentlyPlayingFile = null,
            searchQuery = mutableStateOf(""),
            onPlayClick = {},
            onStopClick = {},
            onDeleteClick = {},
            onSearchQueryChange = {},
            onRefresh = {}
        )
    }
}