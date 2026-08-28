/*
 * Article width preference (docs supplemental UI).
 *
 * Modes (one toolbar control cycles them):
 *   default — comfortable reading measure on .doc
 *   wide    — fixed ~56rem from ≥1024px
 *   full    — fill the article column for very wide console samples
 *
 * Classes on <html>: cuppa-doc-wide | cuppa-doc-full (mutually exclusive).
 * Preference: localStorage STORAGE_KEY = "wide" | "full" (absent = default).
 *
 * An early script in head-styles.hbs applies the class before paint to avoid a
 * width flash; this file wires the toolbar button and keeps aria/title in sync.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'cuppa-doc-width';
  var MODE_DEFAULT = 'default';
  var MODE_WIDE = 'wide';
  var MODE_FULL = 'full';
  var CLASS_WIDE = 'cuppa-doc-wide';
  var CLASS_FULL = 'cuppa-doc-full';
  var ORDER = [ MODE_DEFAULT, MODE_WIDE, MODE_FULL ];

  function currentMode() {
    var root = document.documentElement;
    if( root.classList.contains( CLASS_FULL ) ){
      return MODE_FULL;
    }
    if( root.classList.contains( CLASS_WIDE ) ){
      return MODE_WIDE;
    }
    return MODE_DEFAULT;
  }

  function readPreference() {
    try {
      var value = localStorage.getItem( STORAGE_KEY );
      if( value === MODE_WIDE || value === MODE_FULL ){
        return value;
      }
    }catch( error ){
      /* private mode / blocked storage */
    }
    return MODE_DEFAULT;
  }

  function writePreference( mode ) {
    try {
      if( mode === MODE_WIDE || mode === MODE_FULL ){
        localStorage.setItem( STORAGE_KEY, mode );
      }else{
        localStorage.removeItem( STORAGE_KEY );
      }
    }catch( error ){
      /* Ignore quota / private-mode failures; the session class still applies. */
    }
  }

  function applyMode( mode ) {
    var root = document.documentElement;
    root.classList.toggle( CLASS_WIDE, mode === MODE_WIDE );
    root.classList.toggle( CLASS_FULL, mode === MODE_FULL );
    writePreference( mode );
    syncButton();
  }

  function nextMode( mode ) {
    var index = ORDER.indexOf( mode );
    if( index < 0 ){
      return MODE_WIDE;
    }
    return ORDER[ ( index + 1 ) % ORDER.length ];
  }

  function labelForNext( mode ) {
    if( mode === MODE_DEFAULT ){
      return 'Widen article';
    }
    if( mode === MODE_WIDE ){
      return 'Use full article width';
    }
    return 'Use comfortable article width';
  }

  function syncButton() {
    var button = document.querySelector( '.cuppa-doc-width-toggle' );
    if( !button ){
      return;
    }
    var mode = currentMode();
    var label = labelForNext( mode );
    button.setAttribute( 'data-cuppa-doc-width', mode );
    button.setAttribute( 'aria-pressed', mode === MODE_DEFAULT ? 'false' : 'true' );
    button.setAttribute( 'title', label );
    button.setAttribute( 'aria-label', label );
  }

  function init() {
    var preferred = readPreference();
    if( preferred !== currentMode() ){
      applyMode( preferred );
    }else{
      syncButton();
    }

    var button = document.querySelector( '.cuppa-doc-width-toggle' );
    if( !button ){
      return;
    }
    button.addEventListener( 'click', function () {
      applyMode( nextMode( currentMode() ) );
    } );
  }

  if( document.readyState === 'loading' ){
    document.addEventListener( 'DOMContentLoaded', init );
  }else{
    init();
  }
}() );
