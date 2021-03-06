(function($) {
  var defaults = {
    'width': 10,
    'items': Array(),
  }
  
  function addInPos(tr, td, pos) {
  }

  $.vpTable = function(tableNode, options) {
    var opts = $.extend({}, defaults, options)
    var node = $(tableNode)
    var cells = Array()
    var trs = Array()

    return {
      draw: function(offset, customRow, cb) {
        if (!offset) offset=0
      
        function draw(slice, cb) {
          node.removeAttr('prev_date')
          if (!trs.length) {
            $('tr', node).each(function (n,tr) {
              trs[tr.className] = $(tr)
            })
          }
          for (var attr in trs) {
            tr = trs[attr] 
            if (tr) {
              for (var i in slice) {
                var item = slice[i]
                if (!cells[attr])
                  cells[attr] = Array()
                if (cells[attr][i]) {
                  var td = cells[attr][i]
                  td.attr('className', '')
                  td.addClass('item-'+item.id)
                  customRow(node, attr, td, item)
                } else {
                  var td = $('<td/>').addClass('item-'+item.id)
                  customRow(node, attr, td, item)
                  cells[attr][i] = td
                  td.appendTo(tr)
                }
              }
            }
          }
          stylePushes()
          if (cb) cb()
        }
        opts['items'].get(offset, offset+opts['width'], draw, cb)
      }
    }
  }
})(jQuery);
