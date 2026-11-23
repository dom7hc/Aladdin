export const POPUP_BLOCKED =
  'Your browser blocked the new tab. Allow pop-ups for this site, or use Download presentation.'

/**
 * Open a tab synchronously (inside the click), then load the slides into it.
 * Never navigates the current tab: a blocked pop-up becomes an error message.
 */
export async function openInNewTab(
  open: () => Window | null,
  getHtml: () => Promise<string>,
  toUrl: (html: string) => string,
): Promise<void> {
  const tab = open()
  if (!tab) throw new Error(POPUP_BLOCKED)
  tab.opener = null
  try {
    const html = await getHtml()
    if (tab.closed) return
    tab.location.href = toUrl(html)
  } catch (error) {
    tab.close()
    throw error
  }
}
