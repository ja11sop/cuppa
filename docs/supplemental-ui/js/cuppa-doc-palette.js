/*
 * Colour-palette preference (docs supplemental UI).
 *
 * Cycles the cuppa-palette-*.css stylesheets linked from head-styles.hbs.
 * Only one <link data-cuppa-palette> is enabled at a time.
 *
 * Preference: localStorage STORAGE_KEY = palette id (absent = cup-of-tea).
 * An early script in head-styles.hbs enables the stored sheet before paint.
 * Legacy id "mint-tea" (removed as near-duplicate of cup-of-tea) maps to default.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'cuppa-doc-palette';
  var DEFAULT = 'cup-of-tea';
  var ORDER = [
    'cup-of-tea',
    'fine-bone-china',
    'harbour',
    'forest',
    'aubergine',
  ];
  var LABELS = {
    'cup-of-tea': 'Cup of tea',
    'fine-bone-china': 'Fine bone china',
    'harbour': 'Harbour',
    'forest': 'Forest',
    'aubergine': 'Aubergine',
  };

  function links() {
    return document.querySelectorAll( 'link[data-cuppa-palette]' );
  }

  function isValid( id ) {
    return ORDER.indexOf( id ) >= 0;
  }

  function normalizeId( id ) {
    if( id === 'mint-tea' ){
      return DEFAULT;
    }
    return id;
  }

  function readPreference() {
    try {
      var value = normalizeId( localStorage.getItem( STORAGE_KEY ) );
      if( isValid( value ) ){
        return value;
      }
    }catch( error ){
      /* private mode / blocked storage */
    }
    return DEFAULT;
  }

  function writePreference( id ) {
    try {
      if( id === DEFAULT ){
        localStorage.removeItem( STORAGE_KEY );
      }else{
        localStorage.setItem( STORAGE_KEY, id );
      }
    }catch( error ){
      /* Ignore quota / private-mode failures; the session sheet still applies. */
    }
  }

  function currentPalette() {
    var nodes = links();
    var i;
    for( i = 0; i < nodes.length; i++ ){
      if( !nodes[ i ].disabled ){
        var id = nodes[ i ].getAttribute( 'data-cuppa-palette' );
        if( isValid( id ) ){
          return id;
        }
      }
    }
    return DEFAULT;
  }

  function applyPalette( id ) {
    if( !isValid( id ) ){
      id = DEFAULT;
    }
    var nodes = links();
    var i;
    for( i = 0; i < nodes.length; i++ ){
      nodes[ i ].disabled =
        nodes[ i ].getAttribute( 'data-cuppa-palette' ) !== id;
    }
    writePreference( id );
    syncButton();
  }

  function nextPalette( id ) {
    var index = ORDER.indexOf( id );
    if( index < 0 ){
      return DEFAULT;
    }
    return ORDER[ ( index + 1 ) % ORDER.length ];
  }

  function labelForNext( id ) {
    var next = nextPalette( id );
    return 'Use ' + LABELS[ next ] + ' palette';
  }

  function syncButton() {
    var button = document.querySelector( '.cuppa-doc-palette-toggle' );
    if( !button ){
      return;
    }
    var id = currentPalette();
    var label = labelForNext( id );
    button.setAttribute( 'data-cuppa-doc-palette', id );
    button.setAttribute( 'title', label );
    button.setAttribute( 'aria-label', label );
  }

  function init() {
    var preferred = readPreference();
    if( preferred !== currentPalette() ){
      applyPalette( preferred );
    }else{
      syncButton();
    }

    var button = document.querySelector( '.cuppa-doc-palette-toggle' );
    if( !button ){
      return;
    }
    button.addEventListener( 'click', function () {
      applyPalette( nextPalette( currentPalette() ) );
    } );
  }

  if( document.readyState === 'loading' ){
    document.addEventListener( 'DOMContentLoaded', init );
  }else{
    init();
  }
}() );
