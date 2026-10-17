// ========================================
// AI Campus Assistant - Frontend
// ========================================

const API_BASE = "http://127.0.0.1:8001/api";
const TOKEN_KEY = "campus_token";
const USER_KEY = "campus_user";

let assignments = [];

// ---------- Элементүүд ----------
const authSection = document.getElementById("auth-section");
const appContent = document.getElementById("app-content");
const userInfo = document.getElementById("user-info");
const userNameLabel = document.getElementById("user-name");
const logoutButton = document.getElementById("logout-button");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const authMessage = document.getElementById("auth-message");

const assignmentForm = document.getElementById("assignment-form");
const searchInput = document.getElementById("assignment-search");
const statusFilter = document.getElementById("assignment-status");

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const chatInitialHTML = chatMessages.innerHTML;

// ---------- Token / session ----------
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function saveSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
}

// ---------- API туслах функцууд ----------
async function readError(response, fallback) {
    try {
        const data = await response.json();

        if (typeof data.detail === "string") {
            return data.detail;
        }

        if (Array.isArray(data.detail)) {
            return data.detail.map(item => item.msg).join(" ");
        }
    } catch (error) {
        // JSON биш хариу байж болно
    }

    return fallback;
}

// Нэвтрээгүй хүсэлт (login, register)
async function publicPost(path, payload) {
    return fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
}

// JWT token-той хүсэлт
async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };

    if (options.body) {
        headers["Content-Type"] = "application/json";
    }

    const token = getToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        logout();
        throw new Error("Нэвтрэх хугацаа дууссан. Дахин нэвтэрнэ үү.");
    }

    return response;
}

// ---------- Нэвтрэх хэсгийн UI ----------
function showAuthMessage(text, isError = true) {
    authMessage.textContent = text;
    authMessage.className = isError ? "auth-message error" : "auth-message success";
}

function switchTab(tab) {
    const isLogin = tab === "login";

    loginForm.hidden = !isLogin;
    registerForm.hidden = isLogin;
    tabLogin.classList.toggle("active", isLogin);
    tabRegister.classList.toggle("active", !isLogin);
    authMessage.textContent = "";
}

function showAuth() {
    authSection.hidden = false;
    appContent.hidden = true;
    userInfo.hidden = true;
}

function showApp(user) {
    authSection.hidden = true;
    appContent.hidden = false;
    userInfo.hidden = false;
    userNameLabel.textContent = user.username;
}

function logout() {
    chatSession += 1;
    clearSession();
    assignments = [];
    renderAssignments();
    chatMessages.innerHTML = chatInitialHTML;
    if (typeof chatSubmitButton !== "undefined" && chatSubmitButton) {
        chatSubmitButton.disabled = false;
    }
    searchInput.value = "";
    statusFilter.value = "all";
    showAuth();
}

tabLogin.addEventListener("click", () => switchTab("login"));
tabRegister.addEventListener("click", () => switchTab("register"));
logoutButton.addEventListener("click", logout);

async function loginUser(username, password) {
    const response = await publicPost("/auth/login", { username, password });

    if (!response.ok) {
        throw new Error(await readError(response, "Нэвтэрч чадсангүй."));
    }

    const data = await response.json();
    saveSession(data.access_token, data.user);
    showApp(data.user);
    await loadAssignments();
}

loginForm.addEventListener("submit", async event => {
    event.preventDefault();

    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;

    try {
        await loginUser(username, password);
        loginForm.reset();
        authMessage.textContent = "";
    } catch (error) {
        showAuthMessage(error.message);
    }
});

registerForm.addEventListener("submit", async event => {
    event.preventDefault();

    const payload = {
        username: document.getElementById("register-username").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: document.getElementById("register-password").value,
        country: document.getElementById("register-country").value.trim() || "Other",
        preferred_language: document.getElementById("register-language").value
    };

    try {
        const response = await publicPost("/auth/register", payload);

        if (!response.ok) {
            throw new Error(await readError(response, "Бүртгүүлж чадсангүй."));
        }

        // Бүртгүүлсний дараа автоматаар нэвтрүүлнэ
        await loginUser(payload.username, payload.password);
        registerForm.reset();
        authMessage.textContent = "";
    } catch (error) {
        showAuthMessage(error.message);
    }
});

// ---------- Даалгавар ----------
async function loadAssignments() {
    try {
        const response = await apiFetch("/assignments");

        if (!response.ok) {
            throw new Error("Даалгавар уншиж чадсангүй.");
        }

        assignments = await response.json();
        renderAssignments();
    } catch (error) {
        console.error("API алдаа:", error);
        if (getToken()) {
            alert("Даалгавар уншиж чадсангүй. Backend ажиллаж байгаа эсэхийг шалгана уу.");
        }
    }
}

async function addAssignment(title, course, deadline) {
    try {
        const response = await apiFetch("/assignments", {
            method: "POST",
            body: JSON.stringify({ title, course, deadline })
        });

        if (!response.ok) {
            throw new Error(await readError(response, "Даалгавар нэмэхэд алдаа гарлаа."));
        }

        await loadAssignments();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

async function toggleAssignment(id) {
    const assignment = assignments.find(item => item.id === id);
    if (!assignment) return;

    try {
        const response = await apiFetch(`/assignments/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ completed: !assignment.completed })
        });

        if (!response.ok) {
            throw new Error("Төлөв шинэчилж чадсангүй.");
        }

        await loadAssignments();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

async function deleteAssignment(id) {
    if (!confirm("Энэ даалгаврыг устгах уу?")) return;

    try {
        const response = await apiFetch(`/assignments/${id}`, {
            method: "DELETE"
        });

        if (!response.ok) {
            throw new Error("Даалгавар устгаж чадсангүй.");
        }

        await loadAssignments();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

function renderAssignments() {
    const list = document.getElementById("assignment-list");
    const totalCount = document.getElementById("total-count");
    const completedCount = document.getElementById("completed-count");
    const remainingCount = document.getElementById("remaining-count");

    const completed = assignments.filter(item => item.completed).length;

    totalCount.textContent = assignments.length;
    completedCount.textContent = completed;
    remainingCount.textContent = assignments.length - completed;

    const searchText = searchInput.value.trim().toLowerCase();
    const selectedStatus = statusFilter.value;

    const filtered = assignments.filter(item => {
        const matchesSearch =
            item.title.toLowerCase().includes(searchText) ||
            item.course.toLowerCase().includes(searchText);

        const matchesStatus =
            selectedStatus === "all" ||
            (selectedStatus === "completed" && item.completed) ||
            (selectedStatus === "incomplete" && !item.completed);

        return matchesSearch && matchesStatus;
    });

    list.replaceChildren();

    if (assignments.length === 0) {
        const message = document.createElement("p");
        message.textContent = "Одоогоор даалгавар алга.";
        list.appendChild(message);
        return;
    }

    if (filtered.length === 0) {
        const message = document.createElement("p");
        message.textContent = "Тохирох даалгавар олдсонгүй.";
        list.appendChild(message);
        return;
    }

    filtered.forEach(item => {
        const article = document.createElement("article");
        article.className = "assignment-item";

        if (item.completed) {
            article.classList.add("completed");
        } else {
            const today = new Date();
            today.setHours(0, 0, 0, 0);

            const deadlineDate = new Date(item.deadline + "T00:00:00");
            const daysLeft = Math.round(
                (deadlineDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)
            );

            if (daysLeft < 0) {
                article.classList.add("overdue");
            } else if (daysLeft <= 3) {
                article.classList.add("due-soon");
            } else {
                article.classList.add("upcoming");
            }
        }

        const info = document.createElement("div");

        const title = document.createElement("h3");
        title.textContent = item.title;

        const course = document.createElement("p");
        course.textContent = `Хичээл: ${item.course}`;

        const deadline = document.createElement("p");
        deadline.textContent = `Дуусах хугацаа: ${item.deadline}`;

        info.append(title, course, deadline);

        const actions = document.createElement("div");
        actions.className = "assignment-actions";

        const completeButton = document.createElement("button");
        completeButton.type = "button";
        completeButton.textContent = item.completed ? "Буцаах" : "Дууссан";
        completeButton.addEventListener("click", () => toggleAssignment(item.id));

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "delete-button";
        deleteButton.textContent = "Устгах";
        deleteButton.addEventListener("click", () => deleteAssignment(item.id));

        actions.append(completeButton, deleteButton);
        article.append(info, actions);
        list.appendChild(article);
    });
}

assignmentForm.addEventListener("submit", async event => {
    event.preventDefault();

    const title = document.getElementById("assignment-title").value.trim();
    const course = document.getElementById("assignment-course").value.trim();
    const deadline = document.getElementById("assignment-deadline").value;

    if (!title || !course || !deadline) {
        alert("Бүх талбарыг бөглөнө үү.");
        return;
    }

    await addAssignment(title, course, deadline);
    assignmentForm.reset();
});

searchInput.addEventListener("input", renderAssignments);
statusFilter.addEventListener("change", renderAssignments);

// ---------- Чат ----------
// Гарах (logout) бүрд нэмэгдэнэ. Хариу ирэхээс өмнө хэрэглэгч гарсан бол
// хуучин хэрэглэгчийн хариуг шинэ хэрэглэгчид харуулахгүй.
let chatSession = 0;
const chatSubmitButton = chatForm.querySelector("button[type='submit'], button");

const SOURCE_LABELS = {
    gemini: "AI · Gemini",
    claude: "AI · Claude",
    rules: "Дүрмийн зөвлөмж",
    local: "Офлайн хариу"
};

// "**тод**" хэсгийг <strong> болгоно. HTML-ийг шууд оруулахгүй (XSS-ээс хамгаална).
function appendInline(parent, text) {
    text.split("**").forEach((part, index) => {
        if (!part) return;
        if (index % 2 === 1) {
            const strong = document.createElement("strong");
            strong.textContent = part;
            parent.appendChild(strong);
        } else {
            parent.appendChild(document.createTextNode(part));
        }
    });
}

// AI-ийн markdown хариуг аюулгүй DOM болгож харуулна:
// "* " эсвэл "- " → жагсаалт, "1. " → дугаартай жагсаалт, бусад → догол мөр.
function renderMarkdown(container, markdown) {
    let currentList = null;
    let currentItem = null;

    markdown.split("\n").forEach(rawLine => {
        const line = rawLine.trim();

        if (!line) {
            currentList = null;
            currentItem = null;
            return;
        }

        const bullet = line.match(/^[*-]\s+(.*)$/);
        const numbered = line.match(/^\d+\.\s+(.*)$/);

        if (bullet || numbered) {
            const listTag = bullet ? "UL" : "OL";
            if (!currentList || currentList.tagName !== listTag) {
                currentList = document.createElement(listTag.toLowerCase());
                container.appendChild(currentList);
            }
            currentItem = document.createElement("li");
            appendInline(currentItem, (bullet || numbered)[1]);
            currentList.appendChild(currentItem);
            return;
        }

        // Жагсаалтын мөрийн дараах тайлбар мөр нь тухайн мөрийн хэсэг
        if (currentItem && /^\s{2,}/.test(rawLine)) {
            currentItem.appendChild(document.createElement("br"));
            appendInline(currentItem, line);
            return;
        }

        currentList = null;
        currentItem = null;
        const paragraph = document.createElement("p");
        appendInline(paragraph, line);
        container.appendChild(paragraph);
    });
}

function addChatMessage(message, sender, source = null) {
    const element = document.createElement("div");
    element.classList.add("chat-message");
    element.classList.add(sender === "user" ? "user-message" : "bot-message");

    if (sender === "user") {
        element.textContent = message;
    } else {
        renderMarkdown(element, message);

        if (source) {
            const badge = document.createElement("span");
            badge.className = `chat-source chat-source-${source}`;
            badge.textContent = SOURCE_LABELS[source] || source;
            element.appendChild(badge);
        }
    }

    chatMessages.appendChild(element);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return element;
}

// Сервертэй холбогдож чадахгүй үед ашиглах хуучин, офлайн хариу
function generateAssistantResponse(question) {
    const text = question.toLowerCase().trim();

    const incompleteTasks = assignments.filter(task => !task.completed);
    const completedTasks = assignments.filter(task => task.completed);

    if (text.includes("хэдэн") && (text.includes("даалгавар") || text.includes("task"))) {
        return `Нийт ${assignments.length} даалгавар байна. Дууссан: ${completedTasks.length}, үлдсэн: ${incompleteTasks.length}.`;
    }

    if (text.includes("дууссан") || text.includes("completed")) {
        if (completedTasks.length === 0) {
            return "Одоогоор дууссан даалгавар алга байна.";
        }
        return "Дууссан даалгаврууд: " + completedTasks.map(task => task.title).join(", ");
    }

    if (text.includes("үлдсэн") || text.includes("дуусаагүй") || text.includes("incomplete")) {
        if (incompleteTasks.length === 0) {
            return "Бүх даалгавар дууссан байна. Баяр хүргэе! 🎉";
        }
        return "Дуусаагүй даалгаврууд: " + incompleteTasks.map(task => task.title).join(", ");
    }

    if (text.includes("ойрын") || text.includes("хугацаа") || text.includes("deadline")) {
        const sorted = incompleteTasks
            .filter(task => task.deadline)
            .sort((a, b) => a.deadline.localeCompare(b.deadline));

        if (sorted.length === 0) {
            return "Хугацаатай дуусаагүй даалгавар олдсонгүй.";
        }

        const task = sorted[0];
        return `Хамгийн ойрын хугацаатай даалгавар: ${task.title}. Дуусах хугацаа: ${task.deadline}.`;
    }

    return "Сервертэй холбогдож чадсангүй. Backend ажиллаж байгаа эсэхийг шалгана уу.";
}

async function askAssistant(question) {
    const response = await apiFetch("/assistant", {
        method: "POST",
        body: JSON.stringify({ question })
    });

    if (!response.ok) {
        throw new Error(await readError(response, "AI туслах хариулж чадсангүй."));
    }

    return response.json();
}

chatForm.addEventListener("submit", async event => {
    event.preventDefault();

    const question = chatInput.value.trim();
    if (!question || chatSubmitButton.disabled) return;

    addChatMessage(question, "user");
    chatInput.value = "";
    chatInput.focus();

    const session = chatSession;
    const pending = addChatMessage("Бодож байна…", "bot");
    pending.classList.add("pending");
    chatSubmitButton.disabled = true;

    try {
        const data = await askAssistant(question);
        if (session !== chatSession) return; // хэрэглэгч гарсан
        pending.remove();
        addChatMessage(data.answer, "bot", data.source);
    } catch (error) {
        if (session !== chatSession) return;
        console.error("Assistant алдаа:", error);
        pending.remove();
        // Нэвтрэх хугацаа дууссан бол apiFetch аль хэдийн logout хийсэн
        if (getToken()) {
            addChatMessage(generateAssistantResponse(question), "bot", "local");
        }
    } finally {
        if (session === chatSession) {
            chatSubmitButton.disabled = false;
        }
    }
});

// ---------- Эхлүүлэх ----------
async function init() {
    if (!getToken()) {
        showAuth();
        return;
    }

    try {
        const response = await apiFetch("/auth/me");

        if (!response.ok) {
            throw new Error("Хэрэглэгчийн мэдээлэл авч чадсангүй.");
        }

        const user = await response.json();
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        showApp(user);
        await loadAssignments();
    } catch (error) {
        console.error(error);
        showAuth();
    }
}

init();