/**
 * Created by yu.zhao
 */

bootbox.setLocale("zh_CN");

function loading(flag){
    var oLoading = $('#loading');
    if (oLoading){
        if(flag){
            oLoading.css('display', 'block');
        }else{
            oLoading.css('display', 'none');
        }
    }
}


$('#change_code').click(function () {
	var username = $(this).attr("username");
	var apicode = $(this).attr("apicode");
	bootbox.confirm('确认更换吗？', function (result) {
	    if (result) {
	        loading(true);
	        $.getJSON("/analyst/changecode/", {username:username,apicode:apicode}, function (ret) {
	            if (ret.msg == 0) {
	                location.reload();
	            } else{
	            	loading(false);
	            	bootbox.alert(ret.msg);
	            }
	        });
	    }
	});
});