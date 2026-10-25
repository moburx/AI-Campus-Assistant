// ========================================
// AI Campus Assistant - Өдрийн цаг ба дэлгэцийн өнгө (theme)
// ========================================
// <html data-daypart="morning|day|evening|night"> → дээд хэсгийн өнгөний туяа, мэндчилгээ
// <html data-theme="light|dark">                   → цайвар / бараан горим
// Хэрэглэгч "Авто / Цайвар / Бараан"-аас сонгоно. Авто үед шөнө бараан болно.

const THEME_KEY = "campus_theme";
const THEME_CHOICES = ["auto", "light", "dark"];
const THEME_CHECK_MINUTES = 5;

const GREETING_KEYS = {
    morning: "welcome.morning",
    day: "welcome.greeting",
    evening: "welcome.evening",
    night: "welcome.night"
};

const themeSelect = document.getElementById("theme-select");

function dayPart(date = new Date()) {
    const hour = date.getHours();
    if (hour >= 5 && hour < 11) return "morning";
    if (hour >= 11 && hour < 17) return "day";
    if (hour >= 17 && hour < 21) return "evening";
    return "night";
}

function loadThemeChoice() {
    try {
        const saved = localStorage.getItem(THEME_KEY);
        return THEME_CHOICES.includes(saved) ? saved : "auto";
    } catch (error) {
        return "auto";
    }
}

let themeChoice = loadThemeChoice();

function resolveTheme(part) {
    if (themeChoice === "auto") {
        return part === "night" ? "dark" : "light";
    }
    return themeChoice;
}

function greetingKey() {
    return GREETING_KEYS[dayPart()];
}

function applyTheme() {
    const part = dayPart();
    const root = document.documentElement;

    root.dataset.daypart = part;
    root.dataset.theme = resolveTheme(part);

    renderGreeting();
    if (currentUser) {
        setThemeColor("app");
    }
}

function setThemeChoice(choice) {
    themeChoice = THEME_CHOICES.includes(choice) ? choice : "auto";

    try {
        localStorage.setItem(THEME_KEY, themeChoice);
    } catch (error) {
        // localStorage ашиглах боломжгүй орчин: энэ удаад л хэрэгжинэ
    }

    applyTheme();
}

themeSelect.value = themeChoice;
themeSelect.addEventListener("change", () => setThemeChoice(themeSelect.value));

// Цаг өнгөрөхөд (жишээ нь 20:59 → 21:00) өнгө, мэндчилгээ шинэчлэгдэнэ.
setInterval(applyTheme, THEME_CHECK_MINUTES * 60 * 1000);

applyTheme();
