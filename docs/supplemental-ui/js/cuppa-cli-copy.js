/**
 * Copy toolbox for colourised Cuppa CLI example blocks
 * (pre.cuppa-output.cuppa-cli-example), matching Antora highlightjs chrome.
 */
(function () {
  'use strict';

  var clipboard = window.navigator.clipboard;
  if( !clipboard ){
    return;
  }

  var uiRoot =
    ( document.getElementById( 'site-script' ) || { dataset: {} } ).dataset
      .uiRootPath
    || ( typeof window.uiRootPath === 'string' ? window.uiRootPath : '.' );

  var svgAs =
    ( document.getElementById( 'site-script' ) || { dataset: {} } ).dataset
      .svgAs;

  function addToolbox( block ) {
    if( block.querySelector( '.source-toolbox' ) ){
      return;
    }
    var pre = block.querySelector( 'pre.cuppa-cli-example' );
    if( !pre ){
      return;
    }
    var code = pre.querySelector( 'code' ) || pre;
    var toolbox = document.createElement( 'div' );
    toolbox.className = 'source-toolbox';

    var button = document.createElement( 'button' );
    button.className = 'copy-button';
    button.setAttribute( 'title', 'Copy to clipboard' );
    button.setAttribute( 'type', 'button' );

    if( svgAs === 'svg' ){
      var svg = document.createElementNS( 'http://www.w3.org/2000/svg', 'svg' );
      svg.setAttribute( 'class', 'copy-icon' );
      var use = document.createElementNS( 'http://www.w3.org/2000/svg', 'use' );
      use.setAttribute( 'href', uiRoot + '/img/octicons-16.svg#icon-clippy' );
      svg.appendChild( use );
      button.appendChild( svg );
    }
    else {
      var img = document.createElement( 'img' );
      img.src = uiRoot + '/img/octicons-16.svg#view-clippy';
      img.alt = 'copy icon';
      img.className = 'copy-icon';
      button.appendChild( img );
    }

    var toast = document.createElement( 'span' );
    toast.className = 'copy-toast';
    toast.appendChild( document.createTextNode( 'Copied!' ) );
    button.appendChild( toast );
    toolbox.appendChild( button );
    block.appendChild( toolbox );

    button.addEventListener( 'click', function () {
      var text = ( code.innerText || code.textContent || '' ).replace( / +$/gm, '' );
      clipboard.writeText( text ).then(
        function () {
          button.classList.add( 'clicked' );
          button.offsetHeight;
          button.classList.remove( 'clicked' );
        },
        function () {}
      );
    } );
  }

  document.querySelectorAll( '.doc .cuppa-cli-block' ).forEach( addToolbox );
})();
