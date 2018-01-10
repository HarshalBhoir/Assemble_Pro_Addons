#
# M0ST_WANT3D
#
{
	"name" : "Biometrics Integration",
	"version" : "1.0",
	"author" : "Vinay Gharat (MSP1 Managed IT Services Pvt Ltd)",
	"category" : "Custom",
	"website" : "www.msp1services.com",
	"description": "ESSL Biometric Device Integration with Odoo",
	"depends" : ["hr_attendance"],
	"data" : [
		'security/biometric_security.xml',
		'security/ir.model.access.csv',
		"views/biometrics_view.xml",
		"views/hr_employee_view.xml",
		"views/hr_all_attendance_view.xml",
		"data/biometrics_data.xml",
	],
	"application": True,
	"installable": True
}
