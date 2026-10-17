// ========================================
// AI Campus Assistant - Эхлүүлэх
// ========================================
// Бусад бүх script ачаалагдсаны дараа хамгийн сүүлд ажиллана.

async function init() {
    fillLanguageSelect(languageSelect);
    fillLanguageSelect(registerLanguage);
    applyTranslations();
    renderAll();

    if (!getToken()) {
        showAuth();
        return;
    }

    try {
        const user = await apiJson("/auth/me");
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        showApp(user);
        await refreshData();
    } catch (error) {
        console.error(error);
        showAuth();
    }
}

init();
