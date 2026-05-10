const statusBox = document.getElementById("status");

let reactionTimer = null;
let activeFace = null;
let activeEffects = [];

function setStatus(msg) {
    statusBox.textContent = msg;
    console.log(msg);
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function getAvatarStageSize() {
    const container = document.getElementById("avatar-stage");
    return {
        container,
        width: container.clientWidth || 320,
        height: container.clientHeight || 420
    };
}

function updateLayout(model, app) {
    const { width, height } = getAvatarStageSize();

    app.renderer.resize(width, height);

    model.anchor.set(0.5, 1);
    model.x = width / 2;
    model.y = height * 3;
    model.scale.set(0.22);
}

async function applyBaseLook(model) {
    const baseExpressions = [
        "remove_watermark",
        "cat_ears_off",
        "wings_off",
        "hair_accessories_off",
        "halo_off",
        "hat_off",
        
    ];

    for (const name of baseExpressions) {
        try {
            console.log("Applying base expression:", name);
            model.expression(name);
            await sleep(180);
        } catch (e) {
            console.warn("Failed base expression:", name, e);
        }
    }
}

function resetFace() {
    if (!window.live2dModel) return;

    console.log("Resetting temporary reactions");

    const temporaryExpressions = [
        "blush",
        "dark_face",
        "dazed_eyes",
        "exclamation",
        "question_mark",
        "v_eyes",
        "star_eyes",
        "tears",
        "angry",
        "sweating_face",
        "speechless_dot",
        "heart",
        "sweat_drop",
        "sleeping",
        "finger_heart",
        "dizzy"
    ];

    for (const name of temporaryExpressions) {
        try {
            window.live2dModel.expression(name);
        } catch (e) {
            console.warn("Reset failed for:", name, e);
        }
    }

    activeFace = null;
    activeEffects = [];
    reactionTimer = null;

    try {
        window.live2dModel.motion("Idle");
    } catch (e) {
        console.warn("Idle reset failed", e);
    }
}

function react(face, effects = []) {
    if (!window.live2dModel) return;

    if (reactionTimer) {
        clearTimeout(reactionTimer);
        reactionTimer = null;
    }

    activeFace = face || null;
    activeEffects = [...effects];

    if (face) {
        try {
            window.live2dModel.expression(face);
        } catch (e) {
            console.warn("Face reaction failed:", face, e);
        }
    }

    effects.forEach(effect => {
        try {
            window.live2dModel.expression(effect);
        } catch (e) {
            console.warn("Effect reaction failed:", effect, e);
        }
    });

    reactionTimer = setTimeout(() => {
        resetFace();
    }, 3000);
}

async function startAvatar() {
    try {
        setStatus("Checking libraries...");

        if (!window.PIXI) throw new Error("PIXI failed to load");
        if (!window.Live2DCubismCore) throw new Error("Cubism Core failed to load");
        if (!PIXI.live2d) throw new Error("Live2D plugin failed to load");
        if (!PIXI.live2d.Live2DModel) throw new Error("Live2DModel class missing");

        const { container, width, height } = getAvatarStageSize();

        const app = new PIXI.Application({
            width,
            height,
            backgroundAlpha: 0,
            antialias: true
        });

        container.appendChild(app.view);

        setStatus("Loading model...");

        const model = await PIXI.live2d.Live2DModel.from(
            "/static/models/nurse.model3.json"
        );

        app.stage.addChild(model);

        window.live2dApp = app;
        window.live2dModel = model;

        updateLayout(model, app);

        try {
            model.motion("Idle");
        } catch (e) {
            console.warn("Idle motion not started:", e);
        }

        await sleep(500);
        await applyBaseLook(model);

        window.addEventListener("resize", () => {
            updateLayout(model, app);
        });

        setStatus("Model loaded successfully");
    } catch (err) {
        console.error(err);
        setStatus("ERROR: " + err.message);
    }
}

startAvatar();

window.avatar = {
    react(face, effects = []) {
        react(face, effects);
    },

    clear() {
        resetFace();
    },

    async reapplyBaseLook() {
        if (!window.live2dModel) return;
        await applyBaseLook(window.live2dModel);
    },

    setScale(scale = 0.22) {
        if (!window.live2dModel) return;
        window.live2dModel.scale.set(scale);
    },

    setPosition(xFactor = 0.5, yFactor = 3) {
        if (!window.live2dModel) return;
        const { width, height } = getAvatarStageSize();
        window.live2dModel.x = width * xFactor;
        window.live2dModel.y = height * yFactor;
    }
};