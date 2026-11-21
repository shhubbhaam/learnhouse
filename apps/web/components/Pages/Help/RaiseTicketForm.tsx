'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ImagePlus, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { Input } from '@components/ui/input'
import { Label } from '@components/ui/label'
import { Textarea } from '@components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { useCourses } from '@/hooks/queries/useCourses'
import { useInvalidateTickets, useTicketsAccessToken } from '@/hooks/queries/useTickets'
import { categoryLabelKey } from '@/lib/tickets/labels'
import { TICKET_CATEGORIES, type TicketCategory } from '@/lib/tickets/types'
import { SUBJECT_MAX, TEXT_MAX, validateTicketForm } from '@/lib/tickets/validation'
import { MAX_ATTACHMENTS, TICKET_IMAGE_TYPES, screenImageFiles } from '@/lib/tickets/attachments'
import { createTicket, uploadTicketAttachment } from '@services/tickets/tickets'

// Radix Select items cannot have an empty value.
const NO_COURSE = 'none'

interface RaiseTicketFormProps {
  orgId?: number
  orgslug: string
  onCreated: (ticketUuid: string) => void
}

export default function RaiseTicketForm({ orgId, orgslug, onCreated }: RaiseTicketFormProps) {
  const { t } = useTranslation()
  const token = useTicketsAccessToken()
  const invalidate = useInvalidateTickets()
  const { data: coursesData } = useCourses(orgslug)

  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<TicketCategory>('TECHNICAL')
  const [courseUuid, setCourseUuid] = useState<string>(NO_COURSE)
  const [touched, setTouched] = useState({ subject: false, description: false })
  const [pending, setPending] = useState(false)
  // Picked locally; uploaded once the ticket exists (uploads need its uuid).
  const [images, setImages] = useState<{ file: File; previewUrl: string }[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const imagesRef = useRef(images)
  imagesRef.current = images
  useEffect(() => () => imagesRef.current.forEach((i) => URL.revokeObjectURL(i.previewUrl)), [])

  const pickImages = (files: File[]) => {
    const { accepted, errors } = screenImageFiles(files, MAX_ATTACHMENTS - images.length)
    errors.forEach((e) => toast.error(t(`tickets.attachments.${e}`)))
    setImages((list) => [...list, ...accepted.map((file) => ({ file, previewUrl: URL.createObjectURL(file) }))])
  }

  const removeImage = (index: number) => {
    setImages((list) => {
      URL.revokeObjectURL(list[index].previewUrl)
      return list.filter((_, i) => i !== index)
    })
  }

  const courses: any[] = useMemo(() => {
    const d: any = coursesData
    if (Array.isArray(d)) return d
    return d?.courses ?? d?.items ?? []
  }, [coursesData])

  const errors = validateTicketForm({ subject, description })
  const isValid = Object.keys(errors).length === 0

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setTouched({ subject: true, description: true })
    if (!isValid || pending || !orgId) return
    setPending(true)
    try {
      const course = courses.find((c) => c.course_uuid === courseUuid)
      const ticket = await createTicket(
        {
          org_id: orgId,
          subject: subject.trim(),
          description: description.trim(),
          category,
          course_id: course ? course.id : null,
        },
        token
      )
      let failed = 0
      for (const img of images) {
        try {
          await uploadTicketAttachment(ticket.ticket_uuid, img.file, { attachToTicket: true }, token!)
        } catch {
          failed += 1
        }
      }
      if (failed > 0) toast.error(t('tickets.attachments.partial_failure'))
      else toast.success(t('help.form.submitted'))
      await invalidate()
      images.forEach((i) => URL.revokeObjectURL(i.previewUrl))
      setImages([])
      setSubject('')
      setDescription('')
      setCategory('TECHNICAL')
      setCourseUuid(NO_COURSE)
      setTouched({ subject: false, description: false })
      onCreated(ticket.ticket_uuid)
    } catch (err: any) {
      toast.error(err?.message || String(err))
    } finally {
      setPending(false)
    }
  }

  const fieldError = (field: 'subject' | 'description') =>
    touched[field] && errors[field] ? (
      <p className="text-xs text-red-600">{t(`help.form.errors.${errors[field]}`)}</p>
    ) : null

  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl bg-white p-5 nice-shadow">
      <div className="space-y-1.5">
        <Label htmlFor="ticket-subject">{t('help.form.subject')}</Label>
        <Input
          id="ticket-subject"
          value={subject}
          maxLength={SUBJECT_MAX + 50}
          placeholder={t('help.form.subject_placeholder')}
          onChange={(e) => setSubject(e.target.value)}
          onBlur={() => setTouched((s) => ({ ...s, subject: true }))}
        />
        {fieldError('subject')}
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>{t('help.form.category')}</Label>
          <Select value={category} onValueChange={(v) => setCategory(v as TicketCategory)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TICKET_CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {t(categoryLabelKey(c))}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label>{t('help.form.course')}</Label>
          <Select value={courseUuid} onValueChange={setCourseUuid}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_COURSE}>{t('help.form.course_none')}</SelectItem>
              {courses.map((c) => (
                <SelectItem key={c.course_uuid} value={c.course_uuid}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ticket-description">{t('help.form.description')}</Label>
        <Textarea
          id="ticket-description"
          value={description}
          rows={6}
          placeholder={t('help.form.description_placeholder')}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => setTouched((s) => ({ ...s, description: true }))}
        />
        <div className="flex justify-between">
          {fieldError('description') ?? <span />}
          <span className="text-xs text-gray-400">
            {description.trim().length}/{TEXT_MAX}
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <input
          ref={fileInput}
          type="file"
          accept={TICKET_IMAGE_TYPES.join(',')}
          multiple
          hidden
          onChange={(e) => {
            pickImages(Array.from(e.target.files || []))
            e.target.value = ''
          }}
        />
        {images.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {images.map((img, i) => (
              <div key={img.previewUrl} className="relative h-20 w-20 overflow-hidden rounded-lg border border-gray-200">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img.previewUrl} alt="" className="h-full w-full object-cover" />
                <button
                  type="button"
                  onClick={() => removeImage(i)}
                  disabled={pending}
                  aria-label={t('tickets.attachments.remove')}
                  className="absolute end-1 top-1 rounded-full bg-black/60 p-0.5 text-white hover:bg-black"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={pending || images.length >= MAX_ATTACHMENTS}
          className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-40"
        >
          <ImagePlus size={14} />
          {t('tickets.attachments.add')} ({images.length}/{MAX_ATTACHMENTS})
        </button>
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={pending || !orgId}
          className="rounded-lg bg-black px-5 py-2 text-xs font-bold text-white nice-shadow transition-all hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {t('help.form.submit')}
        </button>
      </div>
    </form>
  )
}
