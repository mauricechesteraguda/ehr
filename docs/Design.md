Design System v1.0

# Synthetic EHR

A violet-led, light-first system for healthcare admin dashboards: calm surfaces, vivid status colors, soft depth.

## Principles

The thinking behind the look.

**Calm surface, loud signal**\
Neutral dark layers stay quiet so color is reserved for status, data and primary actions.

**One hero, many supports**\
Each screen opens with one violet gradient banner; everything below is flat cards.

**Color means category**\
Green, orange, blue and magenta map to fixed meanings across stats, charts and chips.

**Rounded and soft**\
12 to 20px radii, gentle glows and thin borders instead of hard shadows.

## Color

Brand and semantic colors. Neutrals swap between dark and light themes.

**Primary**`#7C3AED`

**Primary 600**`#6D28D9`

**Primary 300**`#A78BFA`

**Accent**`#A855F7`

**Success / Beds**`#10B981`

**Warning / Appts**`#F59E0B`

**Info / Doctors**`#0EA5E9`

**Danger**`#EF4444`

Neutrals

**Dark bg**`#0F0E1A`

**Dark surface**`#181727`

**Light bg**`#F5F3FF`

**Light surface**`#FFFFFF`

**Hero gradient** `linear-gradient(120deg, #7C3AED, #6D28D9 55%, #4F46E5)`

## Typography

Outfit, a geometric sans. Tight tracking on large sizes, uppercase labels for stat captions.

Display 36`700 / -0.02em`

Page title 26`600`

Card title 20`600`

Body 15, used for paragraphs and table cells.`400 / 1.5`

Caption label 11`500 / +0.06em`

## Spacing and radius

4px base grid. Radii step up with component size.

4

8

12

16

24

32

48

sm 8

md 12

lg 20

pill

## Buttons and inputs

Primary for the main action, white on gradient banners, outline for secondary.

## Stat cards

Accent edge, uppercase label, large number, delta pill, timestamp.

Total patients**2,543**+12%\
`Updated 2m ago`

Available beds**156**+5%\
`Updated 2m ago`

Doctors**89**+8%\
`Updated 2m ago`

Appointments**324**+15%\
`Updated 2m ago`

Snapshot chips

Admissions 124 Discharges 42 Bed Utilization 76% Revenue $48.2k

## Navigation

Sidebar item: 14px label, active state uses the primary gradient.

DashboardAppointmentsPatientsDoctorsPharmacy

**Shell**\
Two-part sidebar: a narrow violet icon rail (64px) beside a 240px label panel. Top bar holds search, context switcher, notifications, theme toggle and a primary-colored profile button. Breadcrumb sits above a right-aligned page title.

## Data visualization

Rounded pill bars, one color per category, smooth single-line trends in primary violet, faint grid.

Series order: violet, green, orange, blue, magenta. Line charts use #8B5CF6 at 2px with 5px point markers.

## Elevation and motion

**Elevation**\
Cards: 1px border plus soft shadow (dark: 0 8px 24px rgba(0,0,0,.45)). Primary buttons get a violet glow.

**Motion**\
150 to 200ms ease-out for hover, focus and menu expand. Charts animate in once on load.