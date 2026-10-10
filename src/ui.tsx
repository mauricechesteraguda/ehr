// type-10042026-Maurice: Ticket02 typed visual primitives and responsive shell.
import { useEffect, useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Activity, AlertCircle, Bell, CheckCircle2, ChevronRight, CircleHelp, Home, Menu, Moon, Search, ShieldAlert, Sun, Users, X } from "lucide-react";
import type { Role } from "./auth";
import { logger } from "./logger";

const uiLog = logger();
type Tone = "primary" | "secondary" | "ghost" | "danger";
type State = "loading" | "empty" | "error" | "no-results";

// type-10042026-Maurice: Button invokes only the caller-provided safe callback.
export function Button({ variant = "primary", loading = false, children, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Tone; loading?: boolean }) {
  return <button {...props} className={`ui-button ui-button--${variant} ${className}`} disabled={props.disabled || loading}>{loading ? "Working…" : children}</button>;
}

// type-10042026-Maurice: IconButton exposes its accessible label as the tooltip contract.
export function IconButton({ label, children, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button {...props} className={`ui-icon-button ${className}`} aria-label={label} title={label}>{children}</button>;
}

// type-10042026-Maurice: Form wrappers preserve native input names and payload semantics.
export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string; children: ReactNode }) {
  const id = useId();
  return <div className="ui-field"><label htmlFor={id}>{label}</label>{children && typeof children === "object" ? children : null}{hint && <small id={`${id}-hint`}>{hint}</small>}{error && <p className="ui-field-error" role="alert">{error}</p>}</div>;
}

// type-10042026-Maurice: Input adds presentation only and does not transform values.
export function Input(props: InputHTMLAttributes<HTMLInputElement>) { return <input {...props} className={`ui-input ${props.className ?? ""}`} />; }
// type-10042026-Maurice: Select adds presentation only and does not transform values.
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) { return <select {...props} className={`ui-input ${props.className ?? ""}`} />; }
// type-10042026-Maurice: TextArea adds presentation only and does not transform values.
export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea {...props} className={`ui-input ${props.className ?? ""}`} />; }

// type-10042026-Maurice: Card is a neutral surface; semantic content remains caller-owned.
export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) { return <section className={`ui-card ${className}`}>{title && <h2>{title}</h2>}{children}</section>; }
export const Panel = Card;

// type-10042026-Maurice: Badge includes text and an icon so meaning is never color-only.
export function Badge({ tone = "info", children }: { tone?: "success" | "warning" | "danger" | "info"; children: ReactNode }) { const Icon = tone === "success" ? CheckCircle2 : tone === "danger" ? ShieldAlert : tone === "warning" ? AlertCircle : CircleHelp; return <span className={`ui-badge ui-badge--${tone}`}><Icon aria-hidden="true" size={14} />{children}</span>; }
// type-10042026-Maurice: StatCard accepts explicit fixture values only.
export function StatCard({ label, value, delta, timestamp }: { label: string; value: string; delta?: string; timestamp?: string }) { return <Card className="ui-stat-card"><span className="ui-caption">{label}</span><strong>{value}</strong>{delta && <Badge tone="success">{delta}</Badge>}{timestamp && <small>{timestamp}</small>}</Card>; }
// type-10042026-Maurice: SnapshotChip presents a bounded dashboard fixture without persistence.
export function SnapshotChip({ label, value }: { label: string; value: string }) { return <span className="ui-snapshot-chip"><span>{label}</span><strong>{value}</strong></span>; }

// type-10042026-Maurice: StatusMessage makes async state explicit in text.
export function StatusMessage({ state, message }: { state: State; message: string }) { const role = state === "error" ? "alert" : "status"; return <div className={`ui-state ui-state--${state}`} role={role} aria-live="polite">{state === "loading" && <Activity aria-hidden="true" size={16} />}{state === "error" && <AlertCircle aria-hidden="true" size={16} />}{message}</div>; }
export const Loading = ({ message = "Loading…" }: { message?: string }) => <StatusMessage state="loading" message={message} />;
export const Empty = ({ message = "Nothing to show." }: { message?: string }) => <StatusMessage state="empty" message={message} />;
export const ErrorState = ({ message = "Unable to load this view." }: { message?: string }) => <StatusMessage state="error" message={message} />;

export type TrendPoint = { label: string; value: number };
// type-10042026-Maurice: TrendChart pairs an accessible SVG with a textual table fallback.
export function TrendChart({ title, points }: { title: string; points: TrendPoint[] }) { const max = Math.max(...points.map((point) => point.value), 1); const pointsAttr = points.map((point, index) => `${(index / Math.max(points.length - 1, 1)) * 100},${100 - (point.value / max) * 90}`).join(" "); return <figure className="ui-chart"><figcaption>{title}</figcaption><svg role="img" aria-label={`${title}. ${points.map((point) => `${point.label}: ${point.value}`).join(", ")}`} viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points={pointsAttr} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />{points.map((point, index) => <circle key={point.label} cx={(index / Math.max(points.length - 1, 1)) * 100} cy={100 - (point.value / max) * 90} r="2" fill="currentColor"><title>{`${point.label}: ${point.value}`}</title></circle>)}</svg><table><caption className="sr-only">{title} data</caption><thead><tr><th scope="col">Period</th><th scope="col">Value</th></tr></thead><tbody>{points.map((point) => <tr key={point.label}><th scope="row">{point.label}</th><td>{point.value}</td></tr>)}</tbody></table></figure>; }

// type-10042026-Maurice: CategoryBarChart includes a non-color textual summary and table.
export function CategoryBarChart({ title, items }: { title: string; items: Array<{ label: string; value: number }> }) { const max = Math.max(...items.map((item) => item.value), 1); return <figure className="ui-chart"><figcaption>{title}</figcaption><p>{items.map((item) => `${item.label}: ${item.value}`).join("; ")}</p><div className="ui-bars" aria-hidden="true">{items.map((item) => <div key={item.label} className="ui-bar-row"><span>{item.label}</span><span className="ui-bar" style={{ "--bar-size": `${(item.value / max) * 100}%` } as React.CSSProperties}>{item.value}</span></div>)}</div><table><caption className="sr-only">{title} data</caption><thead><tr><th scope="col">Category</th><th scope="col">Value</th></tr></thead><tbody>{items.map((item) => <tr key={item.label}><th scope="row">{item.label}</th><td>{item.value}</td></tr>)}</tbody></table></figure>; }

// type-10042026-Maurice: Breadcrumbs use current route state and no browser storage.
export function Breadcrumbs({ items }: { items: Array<{ label: string; href?: string }> }) { return <nav className="ui-breadcrumbs" aria-label="Breadcrumb"><ol>{items.map((item, index) => <li key={item.label}>{item.href && index !== items.length - 1 ? <a href={item.href}>{item.label}</a> : <span aria-current={index === items.length - 1 ? "page" : undefined}>{item.label}</span>}{index < items.length - 1 && <ChevronRight aria-hidden="true" size={14} />}</li>)}</ol></nav>; }

function IconRail({ role, route }: { role: Role; route: string }) { const items = [{ label: "Home", href: "/", icon: Home }, { label: "Patients", href: "/", icon: Users }, { label: "Activity", href: "/", icon: Activity }]; return <aside className="icon-rail" aria-label="Primary shortcuts">{items.map(({ label, href, icon: Icon }) => <a key={label} href={href} className={route === href ? "is-active" : ""} aria-label={label} aria-current={route === href ? "page" : undefined} title={label}><Icon aria-hidden="true" size={20} /></a>)}<span className="icon-rail-role" aria-label={`Signed in role: ${role}`}>{role.slice(0, 1).toUpperCase()}</span></aside>; }

function Sidebar({ role, route, onNavigate }: { role: Role; route: string; onNavigate: (path: string) => void }) { const links = [{ label: "Dashboard", href: "/" }, ...(role === "admin" ? [{ label: "Administration", href: "/admin" }] : []), ...(role === "developer" ? [{ label: "SMART developer", href: "/developer" }] : [])]; return <aside className="sidebar" aria-label="Workspace sections"><div className="sidebar-brand">Synthetic EHR <span>prototype</span></div><nav aria-label="Workspace navigation">{links.map((link) => <button key={link.href} className={route === link.href ? "is-active" : ""} aria-current={route === link.href ? "page" : undefined} onClick={() => onNavigate(link.href)}>{link.label}</button>)}</nav></aside>; }

function TopBar({ role, username, onMenu, onTheme, onSignOut }: { role: Role; username: string; onMenu: () => void; onTheme: () => void; onSignOut?: () => void }) { const [query, setQuery] = useState(""); return <header className="top-bar"><IconButton label="Open navigation" className="mobile-menu" onClick={onMenu}><Menu aria-hidden="true" /></IconButton><div><strong>Workspace</strong><span>{role} · {username}</span></div><label className="top-search"><Search aria-hidden="true" size={16} /><span className="sr-only">Search workspace</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search workspace" /></label><IconButton label="Notifications"><Bell aria-hidden="true" /></IconButton><IconButton label="Toggle theme" onClick={onTheme}><Moon aria-hidden="true" /></IconButton><span className="profile-button" aria-label={`Profile for ${username}`}>{username.slice(0, 1).toUpperCase() || "U"}</span>{onSignOut && <Button variant="ghost" onClick={onSignOut}>Sign out</Button>}</header>; }

// type-10042026-Maurice: ClinicalContextRibbon provides one bounded hero action per screen.
export function ClinicalContextRibbon({ role, page, context, safety, action }: { role: Role; page: string; context: string; safety: string; action: ReactNode }) { return <section className="context-ribbon" aria-labelledby="context-ribbon-title"><div><span className="ui-caption">{role} workspace · {safety}</span><h1 id="context-ribbon-title">{page}</h1><p>{context}</p></div><div>{action}</div></section>; }

// type-10042026-Maurice: AppShell owns route/theme/drawer state in memory only.
export function AppShell({ role, username, route, onNavigate, onSignOut, children, page = "Records", context = "Synthetic workspace for bounded record review.", safety = "Synthetic data only" }: { role: Role; username: string; route: string; onNavigate: (path: string) => void; onSignOut?: () => void; children: ReactNode; page?: string; context?: string; safety?: string }) { const [drawerOpen, setDrawerOpen] = useState(false); const [theme, setTheme] = useState<"dark" | "light">("light"); useEffect(() => { document.documentElement.dataset.theme = theme; return () => { delete document.documentElement.dataset.theme; }; }, [theme]); const changeTheme = () => { setTheme((current) => current === "dark" ? "light" : "dark"); uiLog.info("theme_toggle"); }; const navigate = (path: string) => { setDrawerOpen(false); onNavigate(path); }; return <div className={`app-shell theme-${theme}`}><IconRail role={role} route={route} /><Sidebar role={role} route={route} onNavigate={navigate} /><div className="app-content"><TopBar role={role} username={username} onMenu={() => setDrawerOpen(true)} onTheme={changeTheme} onSignOut={onSignOut} /><div className="page-frame"><a className="skip-link" href="#main-content">Skip to main content</a><Breadcrumbs items={[{ label: "Workspace", href: route === "/" ? undefined : "/" }, { label: page }]} /><ClinicalContextRibbon role={role} page={page} context={context} safety={safety} action={<Button variant="secondary" onClick={() => navigate("/")}>View records</Button>} /><main id="main-content">{children}</main></div></div>{drawerOpen && <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)}><aside className="mobile-drawer" aria-label="Mobile navigation" onClick={(event) => event.stopPropagation()}><div className="drawer-heading"><strong>Navigation</strong><IconButton label="Close navigation" onClick={() => setDrawerOpen(false)}><X aria-hidden="true" /></IconButton></div><Sidebar role={role} route={route} onNavigate={navigate} /></aside></div>}</div>; }
