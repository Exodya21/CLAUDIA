from odoo import _, fields, models
from odoo.exceptions import UserError


class SpBancoImportar(models.TransientModel):
    _name = "sp.banco.importar"
    _description = "Importar extractos bancarios"

    archivo_ids = fields.Many2many("ir.attachment", string="Extractos",
                                   help="Uno o varios: Excel (.xlsx, .xls), Norma 43, CAMT.053 (XML) o CSV.")
    journal_id = fields.Many2one("account.journal", "Cuenta", domain="[('type', '=', 'bank')]",
                                 help="Solo hace falta si el archivo no indica la cuenta: cada extracto va a la cuenta "
                                      "cuyo IBAN termina igual.")
    solo_comprobar = fields.Boolean("Comprobar sin importar", help="Lee los archivos y muestra el resultado sin guardar nada.")

    def action_importar(self):
        if not self.env.user.has_group("sp_recepcion.group_sp_responsable"):
            raise UserError(_("Solo Contabilidad importa extractos."))
        if not self.archivo_ids:
            raise UserError(_("Añada al menos un extracto."))
        importaciones = self.env["sp.banco.importacion"]
        for a in self.archivo_ids:
            raw = a.raw
            importaciones |= importaciones._sp_importar(a.name, getattr(raw, "content", raw), self.journal_id,
                                                        self.solo_comprobar)
        self.archivo_ids.unlink()  # el original queda adjunto a su importación
        return {"type": "ir.actions.act_window", "res_model": "sp.banco.importacion", "view_mode": "list,form",
                "domain": [("id", "in", importaciones.ids)], "name": _("Resultado de la importación")}
