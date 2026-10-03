# mObywatel Design System – Figma AI Prompt

**Role & Context:**
You are an expert UI/UX Designer and Figma AI. Your task is to generate a comprehensive, high-fidelity design system and screen mockups for a civic/digital wallet application based strictly on the official "mObywatel" app guidelines. The aesthetic should be clean, accessible, modern, and highly trustworthy, suitable for a government-level digital identity application.

---

## 1. Color Palette

The color system is organized into semantic and decorative categories. Please create local color styles in Figma using these exact names and roles.

**Primary & Secondary:**
*   `primary900` / `walletPrimary900`: Main brand color (used for primary actions, navigation bars, active states).
*   `secondary900` / `walletSecondary900`: Secondary brand color.
*   `secondary100`, `secondary80`, `secondary30`: Lighter shades for backgrounds and subtle elements.

**Neutrals (Text, Backgrounds, Borders):**
*   `background`: Global app background.
*   `neutral500`: Primary text and dark icons.
*   `neutral300`: Secondary text/icons.
*   `neutral200`: Tertiary text, inactive elements.
*   `neutral100`, `neutral80`, `neutral60`, `neutral30`, `neutral10`: Borders, dividers, disabled states.

**Functional & Status Colors:**
*   **Success / Positive:** `green100`, `green20`, `decorativeGreen80`, `sprouts100`, `grass200`, `grass80`, `grass30`.
*   **Warning / Alert:** `orange100`, `orange20`, `decorativeOrange80`, `sun80`, `sun30`.
*   **Error / Destructive:** `red200`, `red100`, `red20`, `decorativeRed300`, `decorativeRed100`, `burgundy200`, `burgundy100`, `burgundy80`, `burgundy30`.
*   **Information / Action:** `blue100`, `blue20`, `decorativeBlue200`, `ocean400`, `ocean200`, `ocean100`, `ocean80`.

**Other Thematic/Service Colors:**
*   `purple300`, `purple200`, `purple100`, `purple40`, `purple30`
*   `pink200`, `pink100`, `pink80`, `pink40`, `pink30`
*   `celadon200`, `celadon100`, `celadon80`, `celadon30`
*   `steel200`, `steel100`, `steel80`, `steel30`
*   `snow300`, `snow200`, `snow100`, `snow80`, `snow40`, `snow30`

---

## 2. Typography

Use a highly legible, accessible system font (e.g., Inter, Roboto, or SF Pro). 
Create the following text styles:

*   **Navigation / App Bar Title:** Size 18px, Weight: Semibold, Color: `neutral500` or `white` (depending on background).
*   **Body Large Medium (`bodyLargeMedium`):** Used for standard buttons, primary card text, and list items. Size ~16px, Weight: Medium.
*   **Body Medium Medium (`bodyMediumMedium`):** Used for small buttons and secondary UI elements. Size ~14px, Weight: Medium.
*   **Caption/Helper:** Size ~12px, Weight: Regular, Color: `neutral300`.

---

## 3. Spacing System

Strictly adhere to this defined spacing scale (in pixels). Do not use arbitrary values for padding or margins.

*   `spacing25`: 2px
*   `spacing50`: 4px
*   `spacing100`: 8px
*   `spacing150`: 12px
*   `spacing200`: 16px (Standard screen margin)
*   `spacing250`: 20px
*   `spacing300`: 24px
*   `spacing400`: 32px
*   `spacing500`: 40px
*   `spacing600`: 48px
*   `spacing700`: 56px

---

## 4. Corner Radiuses

Use these specific border-radius values for UI components:

*   `radius50`: 4px (Small tags, checkboxes)
*   `radius150`: 12px (Standard component borders, small cards)
*   `radius200`: 16px (Medium cards, dialogs)
*   `radius300`: 24px (Standard Buttons, Bottom sheets)
*   `radius500`: 40px (Large rounded elements)
*   *Note: Standard buttons typically use full pill shapes (CircleShape/radius300).*

---

## 5. Drop Shadows

Implement layered shadows for depth, specifically using two layers per shadow style. Color used for shadow is `neutral500`.

*   **`light200` (Subtle):**
    *   Layer 1: Y: 0, Blur: 2, Opacity: 2%
    *   Layer 2: Y: 8, Blur: 8, Opacity: 4%
*   **`light400` (Medium):**
    *   Layer 1: Y: 0, Blur: 4, Opacity: 2%
    *   Layer 2: Y: 16, Blur: 12, Opacity: 4%
*   **`light600` (Elevated - Modals/Dialogs):**
    *   Layer 1: Y: 0, Blur: 4, Opacity: 2%
    *   Layer 2: Y: 24, Blur: 16, Opacity: 4%

---

## 6. Key UI Components

Design the following components using Auto Layout and the tokens above:

1.  **Buttons:**
    *   *Sizes:* Large (min-height: 48px, padding: 8px vertical, 16px horizontal), Small (min-height: 32px).
    *   *Variants:* 
        *   Primary (Background: `primary900`, Text: `white`)
        *   Secondary (Outline width: 1px, Text/Border: `primary900`, Background: Transparent)
        *   Destructive (Background: `supportRed100` / `red200`)
        *   Disabled (Background: `neutral30`, Text: `neutral60`)
    *   *Shape:* Fully rounded (`radius300` / pill shape).
2.  **Cards (`SingleCard`, `SmallCard`, `DocumentCard`):**
    *   Background: White or light surface.
    *   Corner Radius: `radius150` or `radius200`.
    *   Shadow: `light200` or `light400`.
3.  **Bottom Navigation Bar (`TabBar`):**
    *   Background: `background`.
    *   Inactive Item: `neutral200`.
    *   Active Item: `primary900`.
4.  **Top App Bar (`NavigationBar`):**
    *   Can be transparent with `background` color or solid with `primary900` (wallet theme).
5.  **Form Inputs & Controls:**
    *   Checkboxes and Radio buttons.
    *   Text Areas and Input Fields (with validation states).
    *   Toggle Switches.
6.  **Feedback Elements:**
    *   `SnackBarView`, `StatusBadge`, `InlineAlert`, `EmptyState`.

---

## Action Plan for Figma AI:
Please generate a basic "Wallet Dashboard" and a "Document Detail" screen utilizing this exact token system. Ensure all paddings align with the 8px/12px/16px/24px spacing scale, and apply the dual-layer shadows to floating cards.
