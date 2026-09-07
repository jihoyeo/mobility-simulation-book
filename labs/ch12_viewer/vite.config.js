import { defineConfig } from "vite";

// base 를 상대경로로 두면 `npm run build` 결과를 어느 주소에 올려도 돌아갑니다.
// 깃허브 페이지의 하위 경로에 올릴 때 필요합니다.
export default defineConfig({
  base: "./",
  server: { open: true },
  build: { outDir: "dist", emptyOutDir: true },
});
