/* global React */
/* Tiny SVG icon set — outline 16px stroke 1.5 */
const Icon = ({ name, size = 16, className = "", color = "currentColor" }) => {
  const s = size;
  const stroke = { stroke: color, strokeWidth: 1.5, fill: "none", strokeLinecap: "round", strokeLinejoin: "round" };
  const paths = {
    inbox: <><path d="M3 13l3-7h8l3 7" {...stroke}/><path d="M3 13v4h14v-4h-4l-1.5 2h-3L7 13H3z" {...stroke}/></>,
    portfolio: <><rect x="3" y="3" width="6" height="6" rx="1" {...stroke}/><rect x="11" y="3" width="6" height="6" rx="1" {...stroke}/><rect x="3" y="11" width="6" height="6" rx="1" {...stroke}/><rect x="11" y="11" width="6" height="6" rx="1" {...stroke}/></>,
    users: <><circle cx="7" cy="7" r="3" {...stroke}/><path d="M2 17c0-2.8 2.2-5 5-5s5 2.2 5 5" {...stroke}/><circle cx="14" cy="8" r="2.2" {...stroke}/><path d="M18 17c0-2.2-1.8-4-4-4" {...stroke}/></>,
    case: <><path d="M3 7h14v9H3z" {...stroke}/><path d="M7 7V5h6v2" {...stroke}/></>,
    shield: <><path d="M10 3l6 2v5c0 4-3 6-6 7-3-1-6-3-6-7V5l6-2z" {...stroke}/></>,
    eye: <><path d="M2 10s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5z" {...stroke}/><circle cx="10" cy="10" r="2.2" {...stroke}/></>,
    flag: <><path d="M5 3v14" {...stroke}/><path d="M5 4h9l-1.5 3L14 10H5" {...stroke}/></>,
    file: <><path d="M5 2h7l3 3v13H5z" {...stroke}/><path d="M12 2v4h3" {...stroke}/></>,
    audit: <><path d="M3 5h14M3 10h14M3 15h9" {...stroke}/></>,
    settings: <><circle cx="10" cy="10" r="2.5" {...stroke}/><path d="M10 3v2M10 15v2M3 10h2M15 10h2M5 5l1.5 1.5M13.5 13.5L15 15M5 15l1.5-1.5M13.5 6.5L15 5" {...stroke}/></>,
    search: <><circle cx="9" cy="9" r="5" {...stroke}/><path d="M13 13l3 3" {...stroke}/></>,
    bell: <><path d="M5 14V9a5 5 0 0110 0v5l1 2H4l1-2z" {...stroke}/><path d="M8 17a2 2 0 004 0" {...stroke}/></>,
    chevronD: <><path d="M5 8l5 4 5-4" {...stroke}/></>,
    chevronR: <><path d="M8 5l4 5-4 5" {...stroke}/></>,
    chevronL: <><path d="M12 5l-4 5 4 5" {...stroke}/></>,
    plus: <><path d="M10 4v12M4 10h12" {...stroke}/></>,
    check: <><path d="M4 10l4 4 8-8" {...stroke}/></>,
    x: <><path d="M5 5l10 10M15 5L5 15" {...stroke}/></>,
    arrowUp: <><path d="M10 16V4M5 9l5-5 5 5" {...stroke}/></>,
    arrowDown: <><path d="M10 4v12M5 11l5 5 5-5" {...stroke}/></>,
    arrowRight: <><path d="M4 10h12M11 5l5 5-5 5" {...stroke}/></>,
    filter: <><path d="M3 4h14l-5 6v6l-4-2v-4L3 4z" {...stroke}/></>,
    download: <><path d="M10 3v10M5 9l5 5 5-5M3 17h14" {...stroke}/></>,
    sort: <><path d="M6 4v12M3 13l3 3 3-3M14 16V4M11 7l3-3 3 3" {...stroke}/></>,
    pin: <><path d="M10 3v6M6 9h8l-2 4H8L6 9zM10 13v4" {...stroke}/></>,
    clock: <><circle cx="10" cy="10" r="6.5" {...stroke}/><path d="M10 6v4l3 1.5" {...stroke}/></>,
    globe: <><circle cx="10" cy="10" r="6.5" {...stroke}/><path d="M3.5 10h13M10 3.5c2 2 3 4 3 6.5s-1 4.5-3 6.5c-2-2-3-4-3-6.5s1-4.5 3-6.5z" {...stroke}/></>,
    link: <><path d="M8 12l4-4M7 13l-2 2a2.8 2.8 0 01-4-4l2-2M13 7l2-2a2.8 2.8 0 014 4l-2 2" {...stroke}/></>,
    note: <><path d="M4 4h12v12H4z" {...stroke}/><path d="M7 8h6M7 11h4" {...stroke}/></>,
    escalate: <><path d="M10 4l5 6h-3v6H8v-6H5l5-6z" {...stroke}/></>,
    bolt: <><path d="M11 3l-6 8h4l-1 6 6-8h-4l1-6z" {...stroke}/></>,
    upload: <><path d="M10 14V4M5 9l5-5 5 5M3 17h14" {...stroke}/></>,
    sparkle: <><circle cx="10" cy="10" r="2.4" {...stroke}/><path d="M10 4v1.5M10 14.5V16M4 10h1.5M14.5 10H16" {...stroke}/></>,
    moon: <><path d="M16 11.5A6 6 0 1 1 8.5 4a5 5 0 0 0 7.5 7.5z" {...stroke}/></>,
    layout: <><rect x="3" y="3" width="14" height="14" rx="1" {...stroke}/><path d="M3 8h14M8 8v9" {...stroke}/></>,
    refresh: <><path d="M3 10a7 7 0 0 1 12-5l2 2M17 4v3h-3M17 10a7 7 0 0 1-12 5l-2-2M3 16v-3h3" {...stroke}/></>,
    expand: <><path d="M4 8V4h4M16 8V4h-4M4 12v4h4M16 12v4h-4" {...stroke}/></>,
  };
  return (
    <svg width={s} height={s} viewBox="0 0 20 20" className={className} aria-hidden="true">{paths[name]}</svg>
  );
};

window.Icon = Icon;
