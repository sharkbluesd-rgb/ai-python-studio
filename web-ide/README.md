# Python Studio Mobile — Web IDE

The browser-first IDE is a standalone static application. It does not send Python source to FastAPI or another execution server.

## Runtime and editor

- CodeMirror 6 provides Python syntax highlighting, line numbers, bracket matching, indentation, folding, search and autocomplete.
- Pyodide runs Python WebAssembly inside a dedicated Web Worker.
- Project files and editor state are stored in IndexedDB on the device.
- fflate imports and exports project ZIP files.
- The runtime is exposed through \`PyodideRuntimeAdapter\`, so a future Android-native runtime can implement the same interface without replacing the editor or project model.

The Python engine is pinned to the \`pyodide\` npm package version 314.0.8. Runtime core and standard-library assets are copied into the static build. Extra Pyodide wheels and micropip packages are downloaded from the matching jsDelivr distribution when requested.

## Browser constraints

Pyodide is Python compiled to WebAssembly, not a native Android Python installation. It cannot provide general Linux shell access, arbitrary system processes, native Android APIs, unrestricted sockets, or compatibility with every PyPI package. Packages must have pure-Python wheels or a compatible Pyodide/WebAssembly build.

Interactive \`input()\` and cooperative KeyboardInterrupt require \`SharedArrayBuffer\`, which in turn requires a secure origin and cross-origin isolation headers (COOP and COEP). The supplied \`public/_headers\` file configures those headers on hosts that support static header files, such as Cloudflare Pages and Netlify. GitHub Pages does not provide custom response headers; there the IDE detects the limitation and uses Web Worker termination as the Stop fallback. It does not pretend that stdin or cooperative interruption is available when the host does not provide it.

Stopping by terminating the Worker really ends that Worker, but it also resets the Python interpreter and any packages installed in that worker. Start it again to create a fresh interpreter.

## Offline behavior

The service worker caches the application shell, local Pyodide runtime files and successfully downloaded Pyodide CDN package assets. After a successful first load and package download, previously cached runtime assets may be available offline. First-time package installation still requires a network connection unless its wheel has already been cached.

## Local development

Requires Node.js 22.12+.

\`\`\`sh
cd web-ide
npm install
npm run dev
\`\`\`

Vite serves the editor at the printed local URL. For full \`input()\` and interrupt support, use an HTTPS host configured with COOP/COEP headers; \`localhost\` is a secure context in supporting browsers.

Build and test:

\`\`\`sh
npm test
npm run build
npm run preview
\`\`\`

## Security and data

Python code runs locally in the user's browser Worker. A Worker prevents a long-running Python loop from blocking the editor UI; it is not a security sandbox. User code can access Pyodide's JavaScript bridge and browser worker APIs. Run only code you trust. IndexedDB data remains in that browser profile and is not uploaded by this web IDE.

Imported ZIP files are size-limited, paths are normalized, and only supported text files are imported. Browser storage can still be cleared by the user or evicted by the browser; export important projects regularly.