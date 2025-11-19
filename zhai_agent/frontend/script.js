// 聊天功能的核心逻辑
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const loginContainer = document.getElementById('login-container');
const chatContainer = document.getElementById('chat-container');
const usernameInput = document.getElementById('username-input');
const loginButton = document.getElementById('login-button');
const logoutButton = document.getElementById('logout-button');
const currentUserSpan = document.getElementById('current-user');

// 当前登录用户信息
let currentUser = {
    name: '',
    id: ''
};

// 初始化页面
function init() {
    // 绑定登录相关事件
    loginButton.addEventListener('click', handleLogin);
    usernameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleLogin();
    });
    logoutButton.addEventListener('click', handleLogout);
    
    // 绑定聊天相关事件
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', handleKeyDown);
    
    // 自动调整输入框高度
    userInput.addEventListener('input', adjustTextareaHeight);
    
    // 检查本地存储中是否有登录信息
    checkSavedLogin();
}

// 处理回车键发送消息
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// 自动调整文本区域高度
function adjustTextareaHeight() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
}

// 发送消息
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;
    
    // 显示用户消息
    displayUserMessage(message);
    
    // 清空输入框
    userInput.value = '';
    adjustTextareaHeight();
    
    // 显示正在输入状态
    const typingIndicator = displayTypingIndicator();
    
    try {
        // 调用实际的API
        const response = await callChatAPI(message);
        
        // 移除正在输入状态
        chatMessages.removeChild(typingIndicator);
        
        // 显示AI回复
        displayBotMessage(response);
    } catch (error) {
        console.error('发送消息错误:', error);
        chatMessages.removeChild(typingIndicator);
        displayBotMessage('抱歉，我暂时无法为您提供服务。请稍后再试。');
    }
}

// 显示用户消息
function displayUserMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message user-message';
    messageElement.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(message)}</p>
        </div>
    `;
    chatMessages.appendChild(messageElement);
    scrollToBottom();
}

// 显示机器人消息
// 1. 新增打字机逻辑函数
function typeWriter(element, text, speed = 30) {
    let i = 0;
    element.innerHTML = ''; // 清空初始内容
    
    // 创建光标元素
    const cursor = document.createElement('span');
    cursor.className = 'typing-cursor';
    cursor.innerHTML = '|';
    element.appendChild(cursor);

    function type() {
        if (i < text.length) {
            // 在光标前插入字符
            cursor.before(text.charAt(i));
            i++;
            // 滚动到底部
            scrollToBottom();
            // 递归调用
            setTimeout(type, speed);
        } else {
            // 打字结束，移除光标
            cursor.remove();
        }
    }
    type();
}

// 2. 修改显示机器人消息的函数
function displayBotMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message bot-message';
    
    // 创建内容容器
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    messageElement.appendChild(contentDiv);
    chatMessages.appendChild(messageElement);
    
    // 调用打字机效果，而不是直接赋值
    // contentDiv.innerHTML = `<p>${escapeHtml(message)}</p>`; // 原代码
    
    // 创建一个 P 标签包裹文本
    const p = document.createElement('p');
    contentDiv.appendChild(p);
    
    typeWriter(p, message); // 启动打字效果
    
    scrollToBottom();
}

// 显示正在输入状态
function displayTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'message bot-message typing-indicator';
    indicator.innerHTML = `
        <div class="message-content">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(indicator);
    scrollToBottom();
    return indicator;
}

// 滚动到底部
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 转义HTML特殊字符
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 生成模拟回复（在API不可用时作为备用）
function generateMockResponse(userMessage) {
    const responses = [
        '感谢您的提问！我正在努力思考如何最好地回答您的问题。',
        '这是一个很好的问题。根据我的理解，您想了解的是关于这个话题的信息。',
        '我很乐意帮助您解决这个问题。让我为您提供一些相关信息。',
        '您的问题很有深度。让我思考一下如何给您一个全面的回答。',
        '根据您的描述，我认为这可能是一个解决方案。您觉得呢？'
    ];
    
    return responses[Math.floor(Math.random() * responses.length)];
}

// 处理登录
async function handleLogin() {
    const username = usernameInput.value.trim();
    if (!username) {
        alert('请输入用户名');
        return;
    }
    
    if (username.length > 20) {
        alert('用户名长度不能超过20个字符');
        return;
    }
    
    try {
        // 调用后端登录API
        const response = await fetch('http://localhost:8000/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username: username })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 设置当前用户信息
            currentUser = {
                name: data.user_name,
                id: data.user_id
            };
            
            // 保存到本地存储
            localStorage.setItem('authToken', data.token);
            localStorage.setItem('userInfo', JSON.stringify(currentUser));
            
            // 更新UI显示
            currentUserSpan.textContent = username;
            
            // 切换显示
            loginContainer.style.display = 'none';
            chatContainer.style.display = 'flex';
            
            // 滚动到底部
            scrollToBottom();
            
            // 清空输入框
            usernameInput.value = '';
            
            // 显示欢迎消息
            const welcomeMessage = `欢迎你，${username}！有什么可以帮助你的吗？`;
            chatMessages.innerHTML = '';
            displayBotMessage(welcomeMessage);
        } else {
            alert(data.message || '登录失败');
        }
    } catch (error) {
        console.error('登录失败:', error);
        alert('登录失败，请稍后再试');
    }
}

// 处理退出
function handleLogout() {
    // 清除本地存储的用户信息
    localStorage.removeItem('userInfo');
    
    // 重置当前用户
    currentUser = { name: '', id: '' };
    
    // 切换显示
    chatContainer.style.display = 'none';
    loginContainer.style.display = 'flex';
    
    // 清空聊天记录
    chatMessages.innerHTML = '';
}

// 检查保存的登录信息
function checkSavedLogin() {
    const savedUserInfo = localStorage.getItem('userInfo');
    if (savedUserInfo) {
        try {
            currentUser = JSON.parse(savedUserInfo);
            currentUserSpan.textContent = currentUser.name;
            loginContainer.style.display = 'none';
            chatContainer.style.display = 'flex';
            scrollToBottom();
        } catch (e) {
            console.error('解析保存的用户信息失败:', e);
            localStorage.removeItem('userInfo');
        }
    }
}

// 实际API调用函数
// 修改 callChatAPI 函数以支持流式读取
async function callChatAPI(message) {
    const token = localStorage.getItem('authToken');
    if (!token) {
        alert('请先登录');
        handleLogout();
        return;
    }

    try {
        const response = await fetch('http://localhost:8000/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) {
            throw new Error('API请求失败');
        }

        // === 核心修改：读取流 ===
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let finalResponse = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // 解码二进制数据块
            const chunk = decoder.decode(value, { stream: true });
            
            // 处理可能的多行数据 (NDJSON)
            const lines = chunk.split('\n').filter(line => line.trim() !== '');
            
            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    
                    // 如果收到的是答案类型
                    if (data.type === 'answer') {
                        finalResponse = data.response;
                        // 这里我们直接返回结果，让外层的 sendMessage 函数去显示
                        // 注意：如果你想实现打字机效果的"流式逐字显示"，逻辑会稍微不同
                        // 但目前的逻辑是：一旦生成完整回复，立即显示，无需等待后续后台任务
                        return finalResponse; 
                    }
                    
                    if (data.type === 'error') {
                        throw new Error(data.response);
                    }
                } catch (e) {
                    console.error("解析流数据出错:", e);
                }
            }
        }
        
        return finalResponse || "未收到有效回复";

    } catch (error) {
        console.error('API调用错误:', error);
        return generateMockResponse(message);
    }
}

// 初始化应用
init();