import { useEffect, useRef, type RefObject } from "react";
import logoUrl from "../../assets/logo.png";

interface MatchaPowderProps {
    // true while the call-to-action is hovered or focused: the grains gather into the logo
    active: boolean;
    // When given, the logo forms just below this element instead of in the middle,
    // so the grains never crowd the text above it
    belowRef?: RefObject<HTMLElement | null>;
}

interface Grain {
    // Resting place, as a fraction of the canvas so it survives a resize
    homeX: number;
    homeY: number;
    // Place in the logo, relative to its centre, as a fraction of the logo size
    logoX: number;
    logoY: number;
    delay: number;
    swirl: number;
    phase: number;
    size: number;
    alpha: number;
    color: string;
}

const COLORS = ["#acd651", "#9cc443", "#c3e27f", "#86ad31"];
const GATHER_SECONDS = 1;
// Space between the element above and the top of the logo, in pixels
const LOGO_GAP = 0;
// Each grain starts its trip somewhere in the first STAGGER of the progress, so
// the logo fills in like falling powder instead of snapping in one block.
const STAGGER = 0.5;

const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

// Every opaque pixel of the logo, centred on (0, 0) and scaled to fit in [-0.5, 0.5].
async function loadLogoPoints(): Promise<[number, number][]> {
    const img = new Image();
    img.src = logoUrl;
    await img.decode();

    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return [];
    ctx.drawImage(img, 0, 0);
    const { data, width, height } = ctx.getImageData(0, 0, canvas.width, canvas.height);

    const side = Math.max(width, height);
    const points: [number, number][] = [];
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            if (data[(y * width + x) * 4 + 3] > 128) {
                points.push([(x - width / 2) / side, (y - height / 2) / side]);
            }
        }
    }
    return points;
}

function makeGrains(points: [number, number][], count: number): Grain[] {
    return Array.from({ length: count }, () => {
        const [logoX, logoY] = points[Math.floor(Math.random() * points.length)];
        return {
            homeX: Math.random(),
            homeY: Math.random(),
            logoX,
            logoY,
            delay: Math.random() * STAGGER,
            swirl: (Math.random() - 0.5) * 0.6,
            phase: Math.random() * Math.PI * 2,
            size: 1 + Math.random() * 1.8,
            alpha: 0.5 + Math.random() * 1,
            color: COLORS[Math.floor(Math.random() * COLORS.length)],
        };
    });
}

export default function MatchaPowder({ active, belowRef }: MatchaPowderProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    // Read by the animation loop, so a hover change never restarts it
    const activeRef = useRef(active);
    useEffect(() => {
        activeRef.current = active;
    }, [active]);

    useEffect(() => {
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext("2d");
        if (!canvas || !ctx) return;

        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        let width = 0;
        let height = 0;
        let grains: Grain[] = [];
        let progress = 0;
        let frame = 0;
        let last = performance.now();
        let cancelled = false;

        const resize = () => {
            const dpr = window.devicePixelRatio || 1;
            width = canvas.clientWidth;
            height = canvas.clientHeight;
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        };
        const observer = new ResizeObserver(resize);
        observer.observe(canvas);
        resize();

        const draw = (now: number) => {
            const dt = Math.min(0.05, (now - last) / 1000);
            last = now;
            const time = now / 1000;

            // Progress moves at a constant speed toward its goal, so leaving the
            // button halfway sends every grain back from exactly where it is.
            const goal = activeRef.current ? 1 : 0;
            const step = dt / GATHER_SECONDS;
            progress = reduceMotion ? goal : goal > progress ? Math.min(goal, progress + step) : Math.max(goal, progress - step);

            let logoSize = Math.min(width, height) * 0.7;
            const centerX = width / 2;
            let centerY = height / 2;
            const above = belowRef?.current;
            if (above) {
                // Read every frame: cheap, and it follows the text through font loads and reflows
                const top = above.getBoundingClientRect().bottom - canvas.getBoundingClientRect().top + LOGO_GAP;
                // Shrink to fit the space left, but never below a recognisable size
                logoSize = Math.max(Math.min(logoSize, height - top - LOGO_GAP), Math.min(width, height) * 0.35);
                centerY = top + logoSize / 2;
            }

            ctx.clearRect(0, 0, width, height);
            for (const g of grains) {
                const t = easeInOutCubic(clamp01((progress - g.delay) / (1 - STAGGER)));
                const drift = reduceMotion ? 0 : 1;
                const homeX = g.homeX * width + Math.sin(time * 0.3 + g.phase) * 14 * drift;
                const homeY = g.homeY * height + Math.cos(time * 0.25 + g.phase * 1.3) * 10 * drift;
                const shimmer = Math.sin(time * 2 + g.phase) * 0.8 * drift;
                const logoX = centerX + g.logoX * logoSize + shimmer;
                const logoY = centerY + g.logoY * logoSize + shimmer;

                // Bend the path sideways in the middle of the trip, like a whisk stroke
                const dx = logoX - homeX;
                const dy = logoY - homeY;
                const bend = Math.sin(Math.PI * t) * g.swirl;
                const x = homeX + dx * t - dy * bend;
                const y = homeY + dy * t + dx * bend;

                ctx.globalAlpha = g.alpha + (0.9 - g.alpha) * t;
                ctx.fillStyle = g.color;
                const size = g.size * (1 + 0.3 * t);
                ctx.fillRect(x, y, size, size);
            }
            ctx.globalAlpha = 1;
            frame = requestAnimationFrame(draw);
        };

        loadLogoPoints().then((points) => {
            if (cancelled || points.length === 0) return;
            const count = Math.round(Math.min(12400, Math.max(1000, (width * height) / 450)));
            grains = makeGrains(points, count);
            frame = requestAnimationFrame(draw);
        });

        return () => {
            cancelled = true;
            cancelAnimationFrame(frame);
            observer.disconnect();
        };
    }, [belowRef]);

    return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full" />;
}
