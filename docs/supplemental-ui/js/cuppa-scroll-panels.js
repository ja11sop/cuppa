/*
 * Wide listing samples — scroll affordances (docs supplemental UI).
 *
 * Goals
 * -----
 * Wide console / JSON samples often overflow the content column. Without help,
 * readers only discover a horizontal scrollbar after scrolling the page to the
 * bottom of a tall block. This script wraps listing/literal <pre> elements and
 * semantic report samples (`pre.cuppa-output`) so:
 *
 *   - Horizontal overflow shows an inset fade + chevron (CSS).
 *   - Grab-drag pans left/right in the sample and up/down on the page.
 *   - Shift+wheel still pans horizontally via the native overflow-x scroller.
 *   - Settling close to an edge snaps flush so the fade can clear.
 *   - Hitting an edge gives a one-shot nudge + accent pulse (not a bounce loop).
 *
 * Non-goals / trade-offs
 * ----------------------
 *   - No vertical scroll *inside* the code frame. Tall samples should be trimmed
 *     in the docs instead; nested vertical scroll traps the page scroll wheel.
 *   - No Alt-key modes or select/pan toggles — grab cursor when overflow-x is
 *     present is enough; the copy button still covers selection for snippets.
 *   - Freezing page-Y during an edge nudge felt worse in practice than allowing
 *     a little vertical drift while the pulse plays — keep vertical live.
 *   - Rubber-band / pointer-lock end feedback was rejected; clamp + rising-edge
 *     latch + accent pulse is clearer on a technical docs site.
 *
 * Edge nudge (rising-edge latch)
 * ------------------------------
 * Pulse only when *entering* overshoot past EDGE_OVERSCROLL_PX. Stay latched
 * while the pointer remains past that edge so scrolling *back* toward the
 * middle does not fire again (a plain cooldown was not enough: after the
 * animation ended, lingering overshoot past the threshold re-pulsed). Clear
 * the latch only after returning inside EDGE_RELEASE_PX (hysteresis). A later
 * intentional push into the same edge can nudge again.
 *
 * Near-edge snap
 * --------------
 * After wheel / trackpad / keyboard scrolling settles, or when a grab ends,
 * snap only if the viewport is already within EDGE_SNAP_PX of an edge. Never
 * snap during a gesture or from the middle. This clears the fade/chevron
 * without making readers overshoot into the resist pulse to prove the edge.
 * A narrow overflow puts both edges in range at once — see edgeSnapTarget for
 * why that resolves to one edge instead of oscillating between them.
 *
 * Smooth scroll
 * -------------
 * Antora's html { scroll-behavior: smooth } makes scrollTop / scrollTo animate.
 * During grab we force scroll-behavior: auto (JS + CSS :has) so pan tracks 1:1.
 */
(function () {
  'use strict';

  var PANEL = 'cuppa-scroll-panel';
  var VIEWPORT = 'cuppa-scroll-panel__viewport';
  // Must match the CSS resist animation duration.
  var RESIST_MS = 280;
  // Ignore tiny horizontal drift while the gesture is mostly vertical.
  var EDGE_OVERSCROLL_PX = 36;
  // Clear the edge latch only after returning well inside the scroll range.
  var EDGE_RELEASE_PX = 8;
  // Close enough to commit to an edge after scrolling settles.
  var EDGE_SNAP_PX = 24;
  // Already flush with an edge; a snap here would be a no-op or a ping-pong.
  var EDGE_SETTLED_PX = 1;
  // Let wheel / trackpad / keyboard input settle before considering a snap.
  var SNAP_SETTLE_MS = 120;

  function scrollRoot() {
    return document.scrollingElement || document.documentElement;
  }

  function pageScrollY() {
    return scrollRoot().scrollTop;
  }

  /*
   * Pair with beginInstantPageScroll / endInstantPageScroll and the CSS
   * html:has(.is-panning) rule. Direct scrollTop writes still animate under
   * scroll-behavior: smooth in Chromium unless behaviour is forced to auto.
   */
  function setPageScrollY( y ) {
    scrollRoot().scrollTop = y;
  }

  function beginInstantPageScroll() {
    var root = scrollRoot();
    root.style.scrollBehavior = 'auto';
  }

  function endInstantPageScroll() {
    var root = scrollRoot();
    root.style.scrollBehavior = '';
  }

  function shouldWrap( pre ) {
    if( pre.closest( '.' + VIEWPORT ) ){
      return false;
    }
    if( !pre.closest( '.doc' ) ){
      return false;
    }
    return pre.classList.contains( 'cuppa-output' )
        || Boolean( pre.closest( '.listingblock, .literalblock' ) );
  }

  /*
   * Measure the <pre>, not only the viewport. Highlighted listings put overflow
   * on an inner width:max-content pre; viewport.scrollWidth alone stays equal
   * to clientWidth and never sets is-scrollable-x (fades and grab never appear).
   */
  function contentWidth( viewport ) {
    var pre = viewport.querySelector( 'pre' );
    if( !pre ){
      return viewport.scrollWidth;
    }
    return Math.max( pre.scrollWidth, pre.offsetWidth, viewport.scrollWidth );
  }

  function maxScrollLeft( viewport ) {
    return Math.max( 0, contentWidth( viewport ) - viewport.clientWidth );
  }

  function pulseEdge( panel, side ) {
    var className = side === 'left' ? 'is-resisting-left' : 'is-resisting-right';
    var timerKey = '_cuppaResistTimer';
    if( panel[ timerKey ] ){
      return false;
    }
    panel.classList.remove( 'is-resisting-left', 'is-resisting-right' );
    // Force a fresh animation start if a class was still lingering.
    void panel.offsetWidth;
    panel.classList.add( className );
    panel[ timerKey ] = window.setTimeout( function () {
      panel.classList.remove( className );
      panel[ timerKey ] = null;
    }, RESIST_MS );
    return true;
  }

  function updateAffordances( panel, viewport ) {
    var sl = viewport.scrollLeft;
    var sw = contentWidth( viewport );
    var cw = viewport.clientWidth;
    var scrollableX = sw > cw + 2;

    panel.classList.toggle( 'is-scrollable-x', scrollableX );
    panel.classList.toggle( 'is-at-start-x', sl <= 2 );
    panel.classList.toggle( 'is-at-end-x', sl + cw >= sw - 2 );
    viewport.classList.toggle( 'is-pan-ready', scrollableX );
  }

  /*
   * Return the edge to commit to, or null to stay put.
   *
   * Overlapping snap zones: when the overflow is smaller than two zones
   * (maxLeft <= 2 * EDGE_SNAP_PX) every position is near both edges. Two rules
   * stop that ping-ponging left-right-left forever. Resting against an edge is
   * final, and an overlap resolves to the nearer edge — stable, because moving
   * there only increases the distance to the edge it rejected.
   */
  function edgeSnapTarget( scrollLeft, maxLeft ) {
    if( maxLeft <= 0 ){
      return null;
    }
    var toStart = scrollLeft;
    var toEnd = maxLeft - scrollLeft;
    // Settled against an edge already (sub-pixel scroll positions included).
    if( toStart <= EDGE_SETTLED_PX || toEnd <= EDGE_SETTLED_PX ){
      return null;
    }
    if( toStart <= EDGE_SNAP_PX && toEnd <= EDGE_SNAP_PX ){
      return toStart <= toEnd ? 0 : maxLeft;
    }
    if( toStart <= EDGE_SNAP_PX ){
      return 0;
    }
    if( toEnd <= EDGE_SNAP_PX ){
      return maxLeft;
    }
    return null;
  }

  function bindPanel( panel, viewport ) {
    viewport.addEventListener(
            'scroll',
            function () {
              updateAffordances( panel, viewport );
              scheduleSnap();
            },
            { passive: true }
    );

    var panning = false;
    var panPointerId = null;
    var startX = 0;
    var startY = 0;
    var startScrollLeft = 0;
    var startPageY = 0;
    var panFrame = 0;
    var pendingClientX = 0;
    var pendingClientY = 0;
    // Rising-edge latch — see file header "Edge nudge".
    var edgeLatched = null;
    var snapTimer = 0;

    function clearScheduledSnap() {
      if( !snapTimer ){
        return;
      }
      window.clearTimeout( snapTimer );
      snapTimer = 0;
    }

    function snapNearEdge() {
      clearScheduledSnap();
      if( panning || !panel.classList.contains( 'is-scrollable-x' ) ){
        return;
      }
      var target = edgeSnapTarget(
              viewport.scrollLeft,
              maxScrollLeft( viewport )
      );
      if( target === null ){
        return;
      }
      var reduceMotion = (
        window.matchMedia
        && window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches
      );
      if( viewport.scrollTo ){
        viewport.scrollTo( {
          left: target,
          behavior: reduceMotion ? 'auto' : 'smooth',
        } );
      }else{
        viewport.scrollLeft = target;
      }
    }

    function scheduleSnap() {
      clearScheduledSnap();
      if( panning ){
        return;
      }
      snapTimer = window.setTimeout( function () {
        snapTimer = 0;
        snapNearEdge();
      }, SNAP_SETTLE_MS );
    }

    function applyPan( clientX, clientY ) {
      var maxLeft = maxScrollLeft( viewport );
      var requestedLeft = startScrollLeft - ( clientX - startX );
      var nextLeft = requestedLeft;
      var overshoot = 0;
      var side = null;

      if( requestedLeft < 0 ){
        nextLeft = 0;
        overshoot = -requestedLeft;
        side = 'left';
      }else if( requestedLeft > maxLeft ){
        nextLeft = maxLeft;
        overshoot = requestedLeft - maxLeft;
        side = 'right';
      }

      viewport.scrollLeft = nextLeft;

      if( side && overshoot >= EDGE_OVERSCROLL_PX ){
        if( edgeLatched !== side ){
          pulseEdge( panel, side );
          edgeLatched = side;
        }
      }else if( !side || overshoot <= EDGE_RELEASE_PX ){
        edgeLatched = null;
      }

      // Always keep page-Y live during grab (including during a nudge pulse).
      setPageScrollY( startPageY - ( clientY - startY ) );
    }

    function schedulePan( clientX, clientY ) {
      pendingClientX = clientX;
      pendingClientY = clientY;
      if( panFrame ){
        return;
      }
      panFrame = window.requestAnimationFrame( function () {
        panFrame = 0;
        if( !panning ){
          return;
        }
        applyPan( pendingClientX, pendingClientY );
      } );
    }

    function endPan() {
      if( !panning ){
        return;
      }
      panning = false;
      panPointerId = null;
      edgeLatched = null;
      if( panFrame ){
        window.cancelAnimationFrame( panFrame );
        panFrame = 0;
      }
      viewport.classList.remove( 'is-panning' );
      panel.classList.remove( 'is-resisting-left', 'is-resisting-right' );
      endInstantPageScroll();
      snapNearEdge();
      if( viewport.blur ){
        viewport.blur();
      }
    }

    /*
     * Pointer events + setPointerCapture keep move/up on this viewport even when
     * the cursor leaves the frame. Avoid tabindex: focusing the viewport after
     * click made wheel / scroll feel wrong relative to the rest of the page.
     */
    viewport.addEventListener( 'pointerdown', function ( event ) {
      if( event.button !== 0 ){
        return;
      }
      if( event.target.closest( '.source-toolbox, .copy-button' ) ){
        return;
      }
      if( !panel.classList.contains( 'is-scrollable-x' ) ){
        return;
      }
      panning = true;
      panPointerId = event.pointerId;
      startX = event.clientX;
      startY = event.clientY;
      startScrollLeft = viewport.scrollLeft;
      startPageY = pageScrollY();
      edgeLatched = null;
      clearScheduledSnap();
      beginInstantPageScroll();
      viewport.classList.add( 'is-panning' );
      if( viewport.setPointerCapture ){
        viewport.setPointerCapture( event.pointerId );
      }
      event.preventDefault();
    } );

    viewport.addEventListener( 'pointermove', function ( event ) {
      if( !panning || event.pointerId !== panPointerId ){
        return;
      }
      schedulePan( event.clientX, event.clientY );
    } );

    viewport.addEventListener( 'pointerup', function ( event ) {
      if( event.pointerId !== panPointerId ){
        return;
      }
      endPan();
    } );

    viewport.addEventListener( 'pointercancel', function ( event ) {
      if( event.pointerId !== panPointerId ){
        return;
      }
      endPan();
    } );

    window.addEventListener( 'mouseup', endPan );

    viewport.addEventListener( 'keydown', function ( event ) {
      if( !panel.classList.contains( 'is-scrollable-x' ) ){
        return;
      }
      var step = 48;
      if( event.key === 'ArrowLeft' ){
        viewport.scrollLeft -= step;
        event.preventDefault();
      }else if( event.key === 'ArrowRight' ){
        viewport.scrollLeft += step;
        event.preventDefault();
      }
    } );

    if( typeof ResizeObserver !== 'undefined' ){
      var observer = new ResizeObserver( function () {
        updateAffordances( panel, viewport );
      } );
      observer.observe( viewport );
      var pre = viewport.querySelector( 'pre' );
      if( pre ){
        observer.observe( pre );
      }
    }
  }

  function wrapPre( pre ) {
    var panel = document.createElement( 'div' );
    panel.className = PANEL;

    var frame = document.createElement( 'div' );
    frame.className = 'cuppa-scroll-panel__frame';

    var viewport = document.createElement( 'div' );
    viewport.className = VIEWPORT;
    viewport.setAttribute(
            'title',
            'Drag to pan: left/right moves the sample, up/down scrolls the page. Shift+scroll pans horizontally.'
    );

    var leftFade = document.createElement( 'div' );
    leftFade.className = 'cuppa-scroll-panel__fade cuppa-scroll-panel__fade--left';
    leftFade.setAttribute( 'aria-hidden', 'true' );

    var rightFade = document.createElement( 'div' );
    rightFade.className = 'cuppa-scroll-panel__fade cuppa-scroll-panel__fade--right';
    rightFade.setAttribute( 'aria-hidden', 'true' );

    pre.parentNode.insertBefore( panel, pre );
    panel.appendChild( frame );
    frame.appendChild( viewport );
    viewport.appendChild( pre );
    frame.appendChild( leftFade );
    frame.appendChild( rightFade );

    bindPanel( panel, viewport );
    updateAffordances( panel, viewport );
  }

  function scheduleMeasure( panel, viewport ) {
    window.requestAnimationFrame( function () {
      updateAffordances( panel, viewport );
      window.requestAnimationFrame( function () {
        updateAffordances( panel, viewport );
      } );
    } );
  }

  function initPre( pre ) {
    if( shouldWrap( pre ) ){
      wrapPre( pre );
      return;
    }
    var viewport = pre.closest( '.' + VIEWPORT );
    if( viewport ){
      scheduleMeasure( viewport.closest( '.' + PANEL ), viewport );
    }
  }

  function init() {
    document.querySelectorAll(
            '.doc .listingblock pre, .doc .literalblock pre, .doc pre.cuppa-output'
    ).forEach( initPre );
  }

  // Collapsed examples measure as zero width until opened — re-wrap / re-measure.
  document.querySelectorAll( '.doc details' ).forEach( function ( details ) {
    details.addEventListener( 'toggle', function () {
      if( !details.open ){
        return;
      }
      details.querySelectorAll(
              '.listingblock pre, .literalblock pre, pre.cuppa-output'
      ).forEach( initPre );
      details.querySelectorAll( '.' + VIEWPORT ).forEach( function ( viewport ) {
        scheduleMeasure( viewport.closest( '.' + PANEL ), viewport );
      } );
    } );
  } );

  if( document.readyState === 'loading' ){
    document.addEventListener( 'DOMContentLoaded', init );
  }else{
    init();
  }
}() );
