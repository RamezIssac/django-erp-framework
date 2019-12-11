/**
 * Created by ramez on 8/20/14.
 */



(function( factory ) {
	if ( typeof define === "function" && define.amd ) {

		// AMD. Register as an anonymous module.
//		define([ "../datepicker" ], factory );
	} else {

		// Browser globals
		factory( jQuery.datepicker );
	}
}(function( datepicker ) {

datepicker.regional['ar'] = {
	closeText: 'إغلاق',
	prevText: '&#x3C;السابق',
	nextText: 'التالي&#x3E;',
	currentText: 'اليوم',
//	monthNames: ['كانون الثاني', 'شباط', 'آذار', 'نيسان', 'مايو', 'حزيران',
//	'تموز', 'آب', 'أيلول',	'تشرين الأول', 'تشرين الثاني', 'كانون الأول'],

    monthNames: ['يناير', 'فبراير', 'مارس', 'ابريل', 'مايو', 'يونيو',
	'يوليو', 'أغسطس', 'سبتمبر',	'أكتوبر', 'نوفمبر', 'ديسمبر'],


	monthNamesShort: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'],
	dayNames: ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'],
	dayNamesShort: ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'],
	dayNamesMin: ['ح', 'ن', 'ث', 'ر', 'خ', 'ج', 'س'],
	weekHeader: 'أسبوع',
	dateFormat: 'dd/mm/yy',
	firstDay: 6,
		isRTL: true,
	showMonthAfterYear: false,
	yearSuffix: ''};
datepicker.setDefaults(datepicker.regional['ar']);

return datepicker.regional['ar'];

}));