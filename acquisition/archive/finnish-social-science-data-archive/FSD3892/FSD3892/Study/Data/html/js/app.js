var last_chars = [' ', '-' ];
var date_format = 'DD.MM.YYYY';

function string_empty(string) {
	return !string || last_chars.indexOf(string) >= 0;
}

$.extend( $.fn.dataTable.ext.type.order, {
"noempty-asc": function ( a, b ) {
	var a_empty = string_empty(a);
	var b_empty = string_empty(b);
	
	if(a_empty && b_empty)
	{
		return 0;
	}	
	else if(a_empty) {
		return 1;
	}
	else if(b_empty) {
		return -1;
	}
	else {
		return a.localeCompare(b);
	}
},
"noempty-desc": function ( a, b ) {
	var a_empty = string_empty(a);
	var b_empty = string_empty(b);
	
	if(a_empty && b_empty)
	{
		return 0;
	}	
	else if(a_empty) {
		return 1;
	}
	else if(b_empty) {
		return -1;
	}
	else {
		return b.localeCompare(a);
	}
}
} );

$.extend( $.fn.dataTable.ext.type.order, {
"datetime-asc": function ( a, b ) {
	var a_date = moment(a, date_format);
	var b_date = moment(b, date_format);
	var a_empty = !a_date.isValid();
	var b_empty = !b_date.isValid();
	
	if(a_empty && b_empty)
	{
		return 0;
	}	
	else if(a_empty) {
		return 1;
	}
	else if(b_empty) {
		return -1;
	}
	else if(a_date.isBefore(b_date)){
		return -1;
	}
	else
	{
		return 1;
	}
},
"datetime-desc": function ( a, b ) {
	var a_date = moment(a, date_format);
	var b_date = moment(b, date_format);
	var a_empty = !a_date.isValid();
	var b_empty = !b_date.isValid();

	
	if(a_empty && b_empty)
	{
		return 0;
	}	
	else if(a_empty) {
		return 1;
	}
	else if(b_empty) {
		return -1;
	}
	else if(a_date.isBefore(b_date)){
		return 1;
	}
	else
	{
		return -1;
	}
}
} );

jQuery.fn.dataTableExt.aTypes.unshift(
    function ( sData )
    {
			let re = /^[\d\?]+\.[\d\?]+\.[\d\?]+/;
			let trimmed = sData.trim();
			if(re.test(trimmed))
			{
				return 'datetime';
			}
			else
			{
				return 'noempty';
			}
    }
);
/*
bindWithDelay jQuery plugin
Author: Brian Grinstead
MIT license: http://www.opensource.org/licenses/mit-license.php
http://github.com/bgrins/bindWithDelay
http://briangrinstead.com/files/bindWithDelay
Usage:
    See http://api.jquery.com/bind/
    .bindWithDelay( eventType, [ eventData ], handler(eventObject), timeout, throttle )
Examples:
    $("#foo").bindWithDelay("click", function(e) { }, 100);
    $(window).bindWithDelay("resize", { optional: "eventData" }, callback, 1000);
    $(window).bindWithDelay("resize", callback, 1000, true);
*/

(function($) {

$.fn.bindWithDelay = function( type, data, fn, timeout, throttle ) {

    if ( $.isFunction( data ) ) {
        throttle = timeout;
        timeout = fn;
        fn = data;
        data = undefined;
    }

    // Allow delayed function to be removed with fn in unbind function
    fn.guid = fn.guid || ($.guid && $.guid++);

    // Bind each separately so that each element has its own delay
    return this.each(function() {

        var wait = null;

        function cb() {
            var e = $.extend(true, { }, arguments[0]);
            var ctx = this;
            var throttler = function() {
                wait = null;
                fn.apply(ctx, [e]);
            };

            if (!throttle) { clearTimeout(wait); wait = null; }
            if (!wait) { wait = setTimeout(throttler, timeout); }
        }

        cb.guid = fn.guid;

        $(this).bind(type, data, cb);
    });
};

})(jQuery);