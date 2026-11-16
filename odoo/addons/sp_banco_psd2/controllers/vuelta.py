from odoo import http
from odoo.exceptions import UserError
from odoo.http import request


class SpBancoPsd2Vuelta(http.Controller):

    @http.route("/sp_banco_psd2/vuelta", type="http", auth="user", methods=["GET"])
    def vuelta(self, state=None, code=None, error=None, **kw):
        try:
            conexion = request.env["sp.banco.conexion"]._sp_vuelta(state, code, error)
        except UserError as e:
            return request.make_response(str(e), headers=[("Content-Type", "text/plain; charset=utf-8")], status=400)
        return request.redirect(f"/odoo/sp.banco.conexion/{conexion.id}")
