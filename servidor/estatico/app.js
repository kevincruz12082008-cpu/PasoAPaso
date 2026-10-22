// PasoAPaso 2.0 · Mejoras pequeñas de la interfaz web.
// No usa librerías externas y funciona sin internet.

(function () {
  "use strict";

  // Mostrar u ocultar claves.
  document.querySelectorAll("[data-ver-clave]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      const campo = document.getElementById(boton.getAttribute("data-ver-clave"));
      if (!campo) return;
      const oculta = campo.type === "password";
      campo.type = oculta ? "text" : "password";
      boton.textContent = oculta ? "🙈" : "👁";
      boton.setAttribute("aria-label", oculta ? "Ocultar la clave" : "Mostrar la clave");
      campo.focus();
    });
  });

  // Confirmaciones para acciones delicadas.
  document.querySelectorAll("form[data-confirmar]").forEach(function (formulario) {
    formulario.addEventListener("submit", function (evento) {
      const mensaje = formulario.getAttribute("data-confirmar");
      if (mensaje && !window.confirm(mensaje)) {
        evento.preventDefault();
        return;
      }
      const boton = formulario.querySelector("button[type=submit]");
      if (boton) {
        boton.disabled = true;
        boton.dataset.textoOriginal = boton.textContent;
        boton.textContent = "Un momento…";
      }
    });
  });

  // Evitar envíos dobles en los demás formularios.
  document.querySelectorAll("form").forEach(function (formulario) {
    if (formulario.hasAttribute("data-confirmar")) return;
    formulario.addEventListener("submit", function () {
      const boton = formulario.querySelector("button[type=submit]");
      if (!boton) return;
      window.setTimeout(function () {
        boton.disabled = true;
        boton.dataset.textoOriginal = boton.textContent;
        boton.textContent = "Un momento…";
      }, 30);
    });
  });

  // Copiar bloques de texto (por ejemplo, el JSON de una consulta).
  document.querySelectorAll("[data-copiar]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      const destino = document.querySelector(boton.getAttribute("data-copiar"));
      if (!destino) return;
      const texto = destino.textContent || "";
      const listo = function () {
        const original = boton.textContent;
        boton.textContent = "¡Copiado!";
        window.setTimeout(function () { boton.textContent = original; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(texto).then(listo).catch(function () {});
      } else {
        const area = document.createElement("textarea");
        area.value = texto;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try { document.execCommand("copy"); listo(); } catch (error) {}
        document.body.removeChild(area);
      }
    });
  });

  // Ocultar solo los avisos de éxito después de un rato.
  document.querySelectorAll(".aviso-ok").forEach(function (aviso) {
    window.setTimeout(function () {
      aviso.style.transition = "opacity .4s ease";
      aviso.style.opacity = "0";
      window.setTimeout(function () { aviso.style.display = "none"; }, 450);
    }, 9000);
  });

  // Enfocar el primer campo con error si existe.
  const primerError = document.querySelector(".aviso-error");
  if (primerError) {
    primerError.setAttribute("role", "alert");
    const primerCampo = document.querySelector("input:invalid, select:invalid");
    if (primerCampo) primerCampo.focus();
  }
})();
