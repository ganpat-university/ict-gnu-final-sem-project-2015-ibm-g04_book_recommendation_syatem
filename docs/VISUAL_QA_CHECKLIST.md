# Visual QA Checklist (Launch Ready)

Use this checklist before demo/submission to verify frontend quality.

## 1) Core Navigation
- Navbar opens/closes correctly on mobile.
- Avatar dropdown opens, closes on outside click, links work.
- Theme toggle persists after refresh (dark/light).
- Search input remains usable in both themes.

## 2) Recommendation UX
- Tabs switch correctly and load content once.
- Skeleton loaders appear before each tab is loaded.
- Carousel arrows scroll horizontally and remain clickable.
- Book cards have consistent height, cover ratio, and hover effects.

## 3) Profile & Checkout
- `/profile` loads user details and selected genres.
- Checked-out books list appears correctly.
- Checkout button from book detail adds to list once (no duplicates).

## 4) Admin Dashboard
- Stat counters animate and stop at real values.
- Activity and audit table filters work for partial text.
- User profile updates save correctly (name/role/MFA/profile fields).
- Clear checked-out action prompts confirmation.

## 5) Messaging & States
- Toast-style flash notifications appear top-right and auto-dismiss.
- Empty states appear for no search results and no checked-out books.
- Error states display readable message (no raw stack traces in UI).

## 6) Responsiveness
- Desktop (>= 1280px): no clipped cards or overlapping controls.
- Tablet (~768px): nav and grids remain readable.
- Mobile (~390px): no horizontal page overflow.

## 7) Accessibility Basics
- Text contrast is readable in both themes.
- Buttons/links are keyboard-focusable.
- Forms have labels/placeholders that match purpose.

## 8) Performance Basics
- First paint does not block on JS.
- No large visual jump while images load.
- Page interactions remain smooth after multiple tab changes.

