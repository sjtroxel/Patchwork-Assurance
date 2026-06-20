import streamlit as st

# Inline-styled HTML because Streamlit has no Tailwind and no native component for an
# icon-link footer (Phase 0 doc 6.2). The GitHub icon links to the repo.
FOOTER_HTML = """
<div style="text-align:center; font-size:10px; color:#888; line-height:1.6; margin-top:2rem;">
  &copy; 2026 sjtroxel
  <a href="https://github.com/sjtroxel/Patchwork-Assurance" target="_blank"
     rel="noopener noreferrer" aria-label="GitHub - Patchwork Assurance"
     style="text-decoration:none; vertical-align:middle; margin:0 2px;">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"
         style="vertical-align:middle;">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
    </svg>
  </a>. All rights reserved.
</div>
"""


# The single controlled CSS layer for the app (Phase 4.5 M4.3). Streamlit theming
# (palette + fonts) lives in .streamlit/config.toml; this style block only covers what
# the theme can't reach: the calm quilt hero banner. One <style> injection, no framework,
# no theming battle (Phase 4 3 still binds).
_BRAND_CSS = """
<style>
  .pa-hero {
    position: relative; overflow: hidden;
    background: linear-gradient(135deg, #2f4b5e 0%, #21304c 100%);
    color: #f3ece1; border-radius: 14px;
    padding: 1.6rem 1.8rem 1.7rem; margin: 0 0 1.4rem;
  }
  /* pieced multi-color seam across the top, the quilt nod at low intensity */
  .pa-hero::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 5px;
    background: linear-gradient(90deg,
      #2f4b5e 0 25%, #7c2f3b 25% 50%, #d6a43e 50% 75%, #2f6f5f 75% 100%);
  }
  .pa-hero .pa-eyebrow {
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700;
    font-size: 0.8rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: #d6a43e; margin: 0 0 0.3rem;
  }
  .pa-hero h1 {
    font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800;
    color: #f3ece1; margin: 0; line-height: 1.1; font-size: clamp(1.6rem, 4vw, 2.3rem);
  }
  .pa-hero p {
    font-family: 'Work Sans', sans-serif; color: #e9ddc9;
    margin: 0.5rem 0 0; font-size: 0.98rem; max-width: 46rem;
  }
  /* the pieced quilt seam, reused as a section divider up and down the page */
  .pa-seam {
    height: 4px; border-radius: 999px; margin: 1.6rem 0;
    background: linear-gradient(90deg,
      #2f4b5e 0 25%, #7c2f3b 25% 50%, #d6a43e 50% 75%, #2f6f5f 75% 100%);
  }
  /* the header logo is the wide 412x64 lockup; show it full-width (mark + outlined
     wordmark). The header img carries class .stLogo + data-testid stHeaderLogo. */
  [data-testid="stLogoLink"] {
    max-width: none !important; width: auto !important; overflow: visible !important;
  }
  img.stLogo,
  [data-testid="stHeaderLogo"],
  [data-testid="stSidebarLogo"] {
    height: 2.1rem !important; width: auto !important;
    max-width: none !important; object-fit: contain !important;
  }
</style>
"""

_SEAM_HTML = '<div class="pa-seam"></div>'


def inject_brand_css() -> None:
    """Inject the one controlled CSS layer (M4.3). Call once at the top of each page."""
    st.markdown(_BRAND_CSS, unsafe_allow_html=True)


def render_seam() -> None:
    """A pieced multi-color quilt seam, used as a brand-forward section divider (M4.2)."""
    st.markdown(_SEAM_HTML, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str) -> None:
    """The app's quilt hero banner - brand continuity with the landing page (M4.2).

    title/subtitle are app-authored constants (no user input), so the inline HTML is safe.
    """
    st.markdown(
        f'<div class="pa-hero"><p class="pa-eyebrow">Patchwork Assurance</p>'
        f"<h1>{title}</h1><p>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )


def render_chrome() -> None:
    """Top-of-page legal chrome - on every surface (ROADMAP 5, 9)."""
    st.warning(
        "Educational tool, not legal advice. Consult a licensed attorney for compliance decisions."
    )
    st.caption("We don't store your inputs - each analysis runs in your session and is discarded.")


def render_footer() -> None:
    """Bottom-of-page footer (the standard mark)."""
    st.markdown(FOOTER_HTML, unsafe_allow_html=True)
