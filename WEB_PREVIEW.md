# Python Studio Mobile — web testing

The browser IDE source is in `web-ide/`. It is built with Vite and deployed as a static application. Python execution happens in a Pyodide Web Worker in the browser; no FastAPI server is used to run user code.

Open the GitHub Pages site after the workflow completes:
`https://sharkbluesd-rgb.github.io/ai-python-studio/`

The production base path is configured for the repository Pages URL. The GitHub Actions workflow builds the Vite app, runs IndexedDB unit tests and the existing Python regression suite, audits the existing Python dependencies, then deploys the Pages artifact.

For full interactive `input()` and cooperative interrupt support, deploy the `web-ide/dist` directory to a host that applies the supplied `web-ide/public/_headers` COOP/COEP headers (Cloudflare Pages or Netlify). GitHub Pages does not accept custom response headers. On GitHub Pages the runtime detects that constraint and uses Worker termination for Stop; it cannot offer terminal stdin or shared-memory interrupts.

Projects are saved in IndexedDB on the user's device. The service worker caches the application, local Pyodide runtime assets and Pyodide CDN package assets after they have been downloaded. A first runtime or package download needs a network connection.
