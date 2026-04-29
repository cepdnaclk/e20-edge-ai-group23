module.exports = {
    // ── Security ──────────────────────────────────────────────────────────────
    credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET || "mysecret",

    // ── HTTP ──────────────────────────────────────────────────────────────────
    httpAdminRoot:  "/",
    httpNodeRoot:   "/api",
    uiPort:         1880,

    // ── Dashboard UI ──────────────────────────────────────────────────────────
    ui: { path: "ui" },

    // ── Logging ───────────────────────────────────────────────────────────────
    logging: {
        console: {
            level:   "info",
            metrics: false,
            audit:   false,
        },
    },

    // ── Editor theme ─────────────────────────────────────────────────────────
    editorTheme: {
        page: {
            title: "Batch Reactor Edge AI",
        },
        header: {
            title: "🏭 Batch Reactor Anomaly Detection",
            image:  null,
        },
        projects: {
            enabled: false,
        },
    },

    // ── Function node extras ──────────────────────────────────────────────────
    functionExternalModules: false,
    functionGlobalContext: {},

    // ── Persistent context ────────────────────────────────────────────────────
    contextStorage: {
        default: { module: "localfilesystem" },
    },
};
