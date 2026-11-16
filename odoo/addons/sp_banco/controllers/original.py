from odoo import http
from odoo.http import request
from odoo.http.stream import content_disposition


class SpBancoOriginal(http.Controller):

    @http.route("/sp_banco/original/<int:imp_id>", type="http", auth="user", methods=["GET"])
    def descargar(self, imp_id, **kw):
        imp = request.env["sp.banco.importacion"].browse(imp_id).exists()
        if not imp:
            raise request.not_found()
        nombre, datos = imp._sp_original_en_claro()  # comprueba el permiso y la huella
        return request.make_response(datos, headers=[
            ("Content-Type", "application/octet-stream"), ("Content-Disposition", content_disposition(nombre)),
            ("Cache-Control", "no-store")])
