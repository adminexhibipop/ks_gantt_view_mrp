import logging
import json

from odoo import api, fields, models, _
from datetime import time, datetime, timedelta
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class KsMrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'

    ks_progress = fields.Char(compute="_compute_workorder_progress")
    ks_task_link_ids = fields.One2many(
        comodel_name='ks.task.link',
        inverse_name='ks_source_wo_id',
        string='Task links')
    ks_task_link_json = fields.Char(compute="ks_compute_json_data_task_link")
    ks_stage_color = fields.Char(compute='ks_compute_order_color')
    ks_schedule_mode = fields.Selection(
        string='Schedule Mode',
        selection=[('auto', 'Auto'),
                   ('manual', 'Manual')],
        default="manual")
    ks_constraint_task_type = fields.Selection(
        string='Constraint Type',
        selection=[('asap', 'As Soon As Possible'),
                   ('alap', 'As Late As Possible'),
                   ('snet', 'Start No Earlier Than'),
                   ('snlt', 'Start No Late Than'),
                   ('fnet', 'Finish No Earlier Than'),
                   ('fnlt', 'Finish No Later Than'),
                   ('mso', 'Must Start On'),
                   ('mfo', 'Must Finish On'),
                   ],
        required=True,
        default="asap")

    ks_constraint_task_date = fields.Datetime(string="Constraint Date")

    def _compute_workorder_progress(self):
        for rec in self:
            duration_count = 0
            for time_track in rec.time_ids:
                duration_count += time_track.duration
            if rec.duration_expected:
                if rec.date_start and rec.date_finished:
                    interval = self.workcenter_id.resource_calendar_id.get_work_duration_data(rec.date_start,
                                                                                              rec.date_finished,
                                                                                              domain=[('time_type', 'in',
                                                                                                       ['leave', 'other'])])
                    if interval['hours'] != 0:
                        rec.duration_expected = interval['hours'] * 60
                rec.ks_progress = duration_count / rec.duration_expected * 100
            else:
                rec.ks_progress = 0

    def ks_compute_json_data_task_link(self):
        for rec in self:
            ks_task_link_json = []
            for task_link in rec.ks_task_link_ids:
                ks_task_link_json.append(
                    {
                        'id': task_link.id,
                        'source': task_link.ks_source_wo_id.id,
                        'target': task_link.ks_target_wo_id.id,
                        'type': task_link.ks_task_link_type,
                    }
                )
            rec.ks_task_link_json = json.dumps(ks_task_link_json)

    def ks_compute_order_color(self):
        """
        Function to compute order color.
        :return:
        """
        ks_gantt_setting = self.env.ref('ks_gantt_view_mrp.ks_gantt_mrp_data_settings')
        for rec in self:
            ks_stage_color = self.env['ks.mrp.gantt.stage.color.wo'].search(
                [('ks_state', '=', rec.state), ('ks_gantt_setting', '=', ks_gantt_setting.id)], limit=1)
            if ks_stage_color and ks_stage_color.ks_color:
                rec.ks_stage_color = ks_stage_color.ks_color
            else:
                rec.ks_stage_color = '#7C7BAD'

    @api.onchange('ks_source_wo_id', 'date_start', 'date_finished','duration_expected')
    def ks_compute_work_duration(self):
        for rec in self:
            if rec.date_start and rec.duration_expected:
                rec.date_finished = rec.date_start + timedelta(minutes=rec.duration_expected)

            elif rec.date_finished and rec.date_start:
                rec.duration_expected = 0
                # if (rec.date_finished - rec.date_start).days == 0:
                    # rec.duration_expected = str(rec.date_finished - rec.date_start) + " hours"
                duration_timedelta = rec.date_finished - rec.date_start
                rec.duration_expected = duration_timedelta.total_seconds() / 3600.0


    def ks_auto_schedule_mode(self):
        """
        Function to calculate order start and end date for schedule record.
        :return:
        """
        if self.ks_schedule_mode == 'auto':

            task_link = self.env['ks.task.link'].search([('ks_target_wo_id', '=', self.id)])
            # find the if task is not linked with other task if not linked then change start date with the
            # project start date
            if not task_link:
                ks_duration = self.date_finished - self.date_start

                if self.ks_constraint_task_type == 'alap':
                    ks_closest_task = False
                    for rec in self.ks_task_link_ids:
                        if rec.ks_source_wo_id.id == self.id:
                            if not ks_closest_task or ks_closest_task > rec.ks_target_wo_id.date_start:
                                ks_closest_task = rec.ks_target_wo_id.date_start

                    if ks_closest_task:
                        self.date_finished = ks_closest_task
                        self.date_start = self.date_finished - ks_duration

            # Current task is attached with other task (Finish to start) as target.
            if len(task_link) == 1 and task_link.ks_task_link_type == "0":
                ks_duration = self.date_finished - self.date_start
                if task_link.ks_source_wo_id.date_finished < self.date_start:
                    self.date_start = task_link.ks_source_wo_id.date_finished
                    self.date_finished = task_link.ks_source_wo_id.date_finished + ks_duration
                else:
                    self.date_finished = task_link.ks_source_wo_id.date_finished + ks_duration
                    self.date_start = task_link.ks_source_wo_id.date_finished

            # Current task is attached with other task (Start to start) as target.
            if len(task_link) == 1 and task_link.ks_task_link_type == "1":
                ks_duration = self.date_finished - self.date_start
                if task_link.ks_source_wo_id.date_start < self.date_start:
                    self.date_start = task_link.ks_source_wo_id.date_start
                    self.date_finished = task_link.ks_source_wo_id.date_start + ks_duration
                else:
                    self.date_finished = task_link.ks_source_wo_id.date_start + ks_duration
                    self.date_start = task_link.ks_source_wo_id.date_start

            # Current task is attached with other task (Finish to finish) as target.
            if len(task_link) == 1 and task_link.ks_task_link_type == "2":
                ks_duration = self.date_finished - self.date_start
                if task_link.ks_source_wo_id.date_finished < self.date_start:
                    self.date_start = task_link.ks_source_wo_id.date_finished - ks_duration
                    self.date_finished = task_link.ks_source_wo_id.date_finished
                else:
                    self.date_finished = task_link.ks_source_wo_id.date_finished
                    self.date_start = task_link.ks_source_wo_id.date_finished - ks_duration

            # Current task is attached with other task (Start to finish) as target.
            if len(task_link) == 1 and task_link.ks_task_link_type == "3":
                ks_duration = self.date_finished - self.date_start
                if task_link.ks_source_wo_id.date_start < self.date_finished:
                    self.date_start = task_link.ks_source_wo_id.date_start - ks_duration
                    self.date_finished = task_link.ks_source_wo_id.date_start
                else:
                    self.date_finished = task_link.ks_source_wo_id.date_start
                    self.date_start = task_link.ks_source_wo_id.date_start - ks_duration

        for rec in self.ks_task_link_ids:
            if rec.ks_target_wo_id.ks_schedule_mode == 'auto':
                rec.ks_target_wo_id.ks_auto_schedule_mode()

    def write(self, values):
        res = super(KsMrpWorkOrder, self).write(values)
        for rec in self:
            if rec.ks_schedule_mode == 'auto' and self.ks_constraint_task_type in ['asap', 'alap']:
                for ks_record in self.ks_task_link_ids:
                    ks_record.ks_target_wo_id.ks_auto_schedule_mode()
            elif rec.date_start or rec.date_finished or rec.ks_task_link_ids:
                # if dates or task link changed from backend then rescheduled its dependent tasks.
                for record in self.ks_task_link_ids:
                    if record.ks_target_wo_id.ks_schedule_mode == 'auto' and \
                            record.ks_target_wo_id.ks_constraint_task_type == 'asap':
                        record.ks_target_wo_id.ks_auto_schedule_mode()

            if rec.ks_constraint_task_type or rec.ks_constraint_task_date:
                rec.ks_validate_constraint()

            # No need to calculate end date if only start datetime is changed.
            # if (rec.ks_task_duration or rec.ks_task_duration == 0) and rec.ks_enable_task_duration \
            #         and not rec.ks_datetime_start:
            #     rec.date_finished = rec.date_start + timedelta(days=rec.ks_task_duration)

        return res

    def ks_validate_constraint(self):
        """
        Function to validate task constraint violation with task start date, end date and constraint date.
        """

        # for constraint type 'Start no earlier than' - the task should start on the constraint date or after it.
        if self.ks_constraint_task_type == 'snet' and not self.ks_constraint_task_date <= self.date_start:
            raise ValidationError(_("Order should be start on the constraint date or after it."))

        # for constraint type 'Start no later than' – the task should start on the constraint date or before it.
        if self.ks_constraint_task_type == 'snlt' and not self.ks_constraint_task_date >= self.date_start:
            raise ValidationError(_("Order should be start on the constraint date or before it."))

        # for constraint type 'Finish no earlier than' – the task should end on the constraint date or after it.
        if self.ks_constraint_task_type == 'fnet' and not self.ks_constraint_task_date <= self.date_finished:
            raise ValidationError(_("Order should be finish on the constraint date or after it."))

        # for constraint type 'Finish no later than' - the task should end on the constraint date or before it.
        if self.ks_constraint_task_type == 'fnlt' and not self.ks_constraint_task_date >= self.date_finished:
            raise ValidationError(_("Order should be finish on the constraint date or before it."))

        # for constraint type 'Must start on' – the task should start exactly on the constraint date.
        if self.ks_constraint_task_type == 'mso' and self.ks_constraint_task_date != self.date_start:
            raise ValidationError(_("Order should start exactly on the constraint date."))

        # for constraint type 'Must finish on' – the task should start exactly on the constraint date.
        if self.ks_constraint_task_type == 'mfo' and self.ks_constraint_task_date != self.date_finished:
            raise ValidationError(_("Order should finish exactly on the constraint date."))