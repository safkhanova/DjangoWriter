"""
Unfold detail/row actions are plain links (GET). Anything that changes state must not run on
GET, or a third-party page could trigger it in a logged-in admin's browser (CSRF). These
actions call `confirm_then`: GET shows a confirmation page, the POSTed form (CSRF token
checked by Django) runs the change.
"""

from django.shortcuts import render


def confirm_then(request, model_admin, *, title, message, run, back_url, button="Təsdiqlə"):
    if request.method == "POST":
        return run()
    context = {
        **model_admin.admin_site.each_context(request),
        "title": title,
        "message": message,
        "button": button,
        "back_url": back_url,
        "opts": model_admin.model._meta,
    }
    return render(request, "admin/confirm_action.html", context)
