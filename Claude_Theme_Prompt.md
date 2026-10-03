# Context for Claude: "Blisko" vs "mObywatel" Integration Concepts

Hi Claude! We are working on a Hackathon project (Smart City Hackyeah) — a P2P offline chat via WiFi Direct that acts as a reliable communication tool during network outages or when telecom towers fail.

We have prepared the UI concept for this app in **two distinct visual variants**, comprising 8 screens each (16 HTML files in total). Here is what you need to know about how they work and why there are two styles:

## 1. The Two Styles
*   **"Blisko" (Standalone App)**: This is our original, independent application concept. It uses its own color palette (green/teal accents, specific neutral backgrounds like `#E8EDF2`). It represents how the app would look if released entirely on its own. These files are named normally, e.g., `01_Home.html`, `02_Chat_List.html`, up to `08_Local_Assistant.html`.
*   **"mObywatel" (Integration Concept)**: This is the exact same application, but styled as if it were a native module inside the official Polish government app, **mObywatel**. It uses a blue color palette (`--primary: #0046FF`), different background shades (`--background: #F3F4F8`), and specific font weights to perfectly mimic the official mObywatel design system. These files are prefixed with `mObywatel_`, e.g., `01_mObywatel_Home.html`.

## 2. How the HTML and Styling Work
*   **Identical Structure**: The HTML DOM structure between the standalone version and the mObywatel version is **100% structurally identical**. 
*   **CSS Variables**: The differences are purely visual and rely heavily on CSS custom properties (variables) defined inline or in stylesheets. For example, a button background will map to `var(--primary, #0046FF)` in the mObywatel version and a different color in the Blisko version.
*   **Layout**: The screens are currently prototyped using absolute positioning and flexbox (`display: inline-flex`, `flex-direction: column`, etc.) within a fixed-width container (`width: 390px; min-height: 900px`).

## 3. Your Role / Next Steps
When analyzing, refactoring, or building logic on top of these screens:
*   Keep in mind that the HTML structure must remain unified so we can easily toggle between the "Standalone" and "mObywatel" themes just by swapping CSS variables or theme classes.
*   Do not hardcode specific colors in the logic; always refer to the CSS variables.
*   Understand that the goal is to demonstrate both paths to the Hackathon jury: our own independent app, and how seamlessly it could be adopted by the state infrastructure.

Feel free to suggest logic implementations, React/Vue component extractions, or P2P WebRTC/WiFi Direct integrations keeping this dual-theme architecture in mind!
